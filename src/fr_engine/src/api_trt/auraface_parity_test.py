"""
Parity test for the AuraFace-v1 models running through fr_engine.

Compares fr_engine's pipeline (any backend, normally TensorRT) against an independent reference
implementation of InsightFace's SCRFD decoding and ArcFace preprocessing on ONNX Runtime CPU,
then checks re-detection of frame-filling close-ups.

Run inside the engine image, e.g.:
    docker run --rm --gpus '"device=0"' -v $PWD/src:/app -v $PWD/models:/models \
        -v $PWD/scratch/converters/test_images:/test_images:ro -w /app --entrypoint python3 \
        census_counters_fr_engine:latest -m api_trt.auraface_parity_test --images /test_images
"""
import argparse
import asyncio
import os
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort
from skimage import transform

from api_trt.modules.configs import config
from api_trt.modules.face_model import FaceAnalysis
from api_trt.modules.utils.image_provider import resize_image

ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                        [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


def nms(dets, thresh):
    x1, y1, x2, y2, scores = dets.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


class RefSCRFD:
    def __init__(self, path):
        self.sess = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
        self.input_name = self.sess.get_inputs()[0].name
        self.output_names = [o.name for o in self.sess.get_outputs()]

    def detect(self, canvas, thresh, nms_thresh=0.4):
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128, canvas.shape[1::-1], (127.5, 127.5, 127.5), swapRB=True)
        outs = self.sess.run(self.output_names, {self.input_name: blob})
        h, w = blob.shape[2:]
        all_scores, all_boxes, all_kps = [], [], []
        for i, stride in enumerate([8, 16, 32]):
            scores = outs[i][:, 0]
            bbox = outs[i + 3] * stride
            kps = outs[i + 6] * stride
            centers = np.stack(np.mgrid[:h // stride, :w // stride][::-1], axis=-1).astype(np.float32)
            centers = np.stack([(centers * stride).reshape(-1, 2)] * 2, axis=1).reshape(-1, 2)
            pos = np.where(scores >= thresh)[0]
            boxes = np.stack([centers[:, 0] - bbox[:, 0], centers[:, 1] - bbox[:, 1],
                              centers[:, 0] + bbox[:, 2], centers[:, 1] + bbox[:, 3]], axis=-1)
            points = np.stack([centers[:, j % 2] + kps[:, j] for j in range(10)], axis=-1).reshape(-1, 5, 2)
            all_scores.append(scores[pos])
            all_boxes.append(boxes[pos])
            all_kps.append(points[pos])
        scores, boxes, kps = np.concatenate(all_scores), np.concatenate(all_boxes), np.concatenate(all_kps)
        if len(scores) == 0:
            return np.zeros((0, 4)), np.zeros(0), np.zeros((0, 5, 2))
        keep = nms(np.hstack([boxes, scores[:, None]]), nms_thresh)
        return boxes[keep], scores[keep], kps[keep]


class RefArcFace:
    def __init__(self, path):
        self.sess = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
        self.input_name = self.sess.get_inputs()[0].name

    def embed(self, crops):
        blob = cv2.dnn.blobFromImages(crops, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
        emb = np.concatenate([self.sess.run(None, {self.input_name: blob[i:i + 1]})[0] for i in range(len(blob))])
        return emb / np.linalg.norm(emb, axis=1, keepdims=True)


def norm_crop(img, kps):
    if hasattr(transform.SimilarityTransform, 'from_estimate'):
        tform = transform.SimilarityTransform.from_estimate(kps, ARCFACE_DST)
    else:
        tform = transform.SimilarityTransform()
        tform.estimate(kps, ARCFACE_DST)
    return cv2.warpAffine(img, tform.params[0:2, :], (112, 112), borderValue=0.0)


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def run(fa, img, threshold):
    return asyncio.run(fa.get([img], extract_embedding=True, extract_ga=False, detect_masks=False,
                              return_face_data=True, threshold=threshold))[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', default='/test_images')
    parser.add_argument('--det', default='auraface_scrfd_10g_bnkps')
    parser.add_argument('--rec', default='auraface_glintr100')
    parser.add_argument('--backend', default='trt')
    parser.add_argument('--threshold', type=float, default=0.6)
    parser.add_argument('--retry_scale', type=float, default=0.5)
    args = parser.parse_args()

    fa = FaceAnalysis(det_name=args.det, rec_name=args.rec, ga_name=None, mask_detector=None,
                      max_size=[640, 640], backend_name=args.backend, root_dir=config.models_dir,
                      det_retry_scale=0.0)
    canvas_size = list(fa.det_model.retina.input_shape[2:][::-1])
    ref_det = RefSCRFD(config.build_model_paths(args.det, 'onnx')[1])
    ref_rec = RefArcFace(config.build_model_paths(args.rec, 'onnx')[1])

    failures = []
    names = sorted(e for e in os.listdir(args.images) if e.lower().endswith(('.jpg', '.jpeg', '.png')))
    print(f'\n== Parity: {args.backend} pipeline vs ONNX Runtime CPU reference (threshold {args.threshold})')
    for name in names:
        img = cv2.imread(os.path.join(args.images, name), cv2.IMREAD_COLOR)
        faces = run(fa, img, args.threshold)
        canvas, scale = resize_image(img, max_size=canvas_size)
        r_boxes, r_scores, r_kps = ref_det.detect(canvas, args.threshold)
        r_boxes, r_kps = r_boxes / scale, r_kps / scale

        ious, kps_err, score_err, cos_backend, cos_full, missed = [], [], [], [], [], 0
        r_embs = ref_rec.embed([norm_crop(img, k) for k in r_kps]) if len(r_kps) else []
        for i in range(len(r_boxes)):
            best = max(range(len(faces)), key=lambda j: iou(r_boxes[i], faces[j]['bbox']), default=None)
            if best is None or iou(r_boxes[i], faces[best]['bbox']) < 0.5:
                if r_scores[i] >= args.threshold + 0.02:
                    missed += 1
                continue
            f = faces[best]
            ious.append(iou(r_boxes[i], f['bbox']))
            kps_err.append(np.abs(f['landmarks'] - r_kps[i]).max() * scale)
            score_err.append(abs(float(f['prob']) - float(r_scores[i])))
            cos_backend.append(float(f['vec'] @ ref_rec.embed([f['facedata']])[0]))
            cos_full.append(float(f['vec'] @ r_embs[i]))

        line = f'{name:14s} faces {args.backend}={len(faces):3d} ref={len(r_boxes):3d} missed={missed}'
        if ious:
            line += (f' | IoU min={min(ious):.3f} | landmark err max={max(kps_err):.2f}px (canvas)'
                     f' | score diff max={max(score_err):.3f}'
                     f' | cos same-crop min={min(cos_backend):.4f} | cos ref-pipeline min={min(cos_full):.4f}')
        print(line)
        if missed:
            failures.append(f'{name}: {missed} reference face(s) not detected')
        if ious and min(ious) < 0.9:
            failures.append(f'{name}: box IoU {min(ious):.3f} < 0.9')
        if cos_backend and min(cos_backend) < 0.99:
            failures.append(f'{name}: same-crop embedding cosine {min(cos_backend):.4f} < 0.99')

    print(f'\n== Close-ups (face filling most of the frame), retry scale {args.retry_scale}')
    for name in names:
        img = cv2.imread(os.path.join(args.images, name), cv2.IMREAD_COLOR)
        fa.det_retry_scale = 0.0
        full = run(fa, img, args.threshold)
        if not full or full[0]['bbox'][2] - full[0]['bbox'][0] < 50:
            continue
        x1, y1, x2, y2 = full[0]['bbox'].astype(int)
        for margin in (0.0, 0.1, 0.25):
            mw, mh = int(margin * (x2 - x1)), int(margin * (y2 - y1))
            crop = img[max(0, y1 - mh):y2 + mh, max(0, x1 - mw):x2 + mw]
            crop = cv2.resize(crop, None, fx=620 / crop.shape[0], fy=620 / crop.shape[0])
            fa.det_retry_scale = 0.0
            plain = run(fa, crop, args.threshold)
            fa.det_retry_scale = args.retry_scale
            retry = run(fa, crop, args.threshold)
            line = f'{name:14s} margin={margin:.2f}: without retry={len(plain)}'
            line += f' (p={plain[0]["prob"]:.2f})' if plain else ''
            line += f' | with retry={len(retry)}'
            if retry:
                line += f' (p={retry[0]["prob"]:.2f}, cos vs full image={float(retry[0]["vec"] @ full[0]["vec"]):.3f})'
            else:
                failures.append(f'{name} close-up margin {margin}: no face even with retry')
            print(line)

    fa.det_retry_scale = 0.0
    img = cv2.imread(os.path.join(args.images, names[0]), cv2.IMREAD_COLOR)
    for _ in range(5):
        run(fa, img, args.threshold)
    t0 = time.perf_counter()
    for _ in range(50):
        run(fa, img, args.threshold)
    print(f'\n== Latency: {(time.perf_counter() - t0) / 50 * 1000:.1f} ms per image '
          f'(detect + align + embed, 1 face, {names[0]})')

    print('\nRESULT:', 'PASS' if not failures else 'FAIL')
    for f in failures:
        print('  -', f)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
