import logging
import os
import time
from typing import Optional, List

import asyncio
import aiohttp
import msgpack
from aiohttp import ClientTimeout, TCPConnector
from fastapi import UploadFile, File, Form, Header, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import UJSONResponse
from fastapi_offline import FastAPIOffline
from starlette.responses import StreamingResponse, RedirectResponse, PlainTextResponse
from contextlib import contextmanager

from api_trt.logger import logger
from api_trt.modules.processing import Processing
from api_trt.schemas import BodyDraw, BodyExtract
from api_trt.settings import Settings

# import faiss
import uuid
import shutil
import numpy as np

from pymilvus import connections, MilvusClient, Collection, FieldSchema, DataType, CollectionSchema

import cv2
import numpy as np
import uuid
import shutil

BLUR_THRESHOLD = 10.0 #120.0  # Tune this based on real data

__version__ = os.getenv('IFR_VERSION','0.9.0.0')

dir_path = os.path.dirname(os.path.realpath(__file__))

# Read runtime settings from environment variables
settings = Settings()

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s %(levelname)s - %(message)s',
    datefmt='[%H:%M:%S]',
)

def search_result_to_dict(search_results):
    result_dict = []
    for hits in search_results:
        for hit in hits:
            hit_dict = {
                "id": hit.id,
                "distance": hit.distance,
                **hit.entity.fields  # This extracts all the fields from the entity
            }
            result_dict.append(hit_dict)
    return result_dict
class MilvusConnectionPool:
    def __init__(self, maxsize):
        self._pool = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize
        self._init_pool()

    def _init_pool(self):
        for _ in range(self._maxsize):
            conn = connections.connect("default", host='census_counters_facedb', port='19530')
            self._pool.put_nowait(conn)

    async def acquire(self):
        return await self._pool.get()

    async def release(self, conn):
        await self._pool.put(conn)

# Create a global connection pool instance
milvus_pool = MilvusConnectionPool(maxsize=8)

async def get_milvus_connection():
    conn = await milvus_pool.acquire()
    try:
        yield conn
    finally:
        await milvus_pool.release(conn)

CLUSTER_ENDPOINT = "http://census_counters_facedb:19530"
FACE_COLLECTION_NAME = 'default'
FACE_COLLECTION_BLACKLIST = 'blacklist'
FACE_INDEX_NAME = 'vector_index'

def drop_collection(client, collection_name: str):
    client.drop_collection(collection_name=collection_name)


def create_collection(client, collection_name: str):
    logger.info(f"Face collection {collection_name} wasn't found, creating it!")

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        metric_type="IP",
        index_type="IVF_FLAT",
        index_name=FACE_INDEX_NAME,
        params={"nlist": 128}
    )

    primary_key = FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
    )

    vector = FieldSchema(
        name="vector",
        dtype=DataType.FLOAT_VECTOR,
        dim=512
    )
    guid = FieldSchema(
        name="guid",
        dtype=DataType.VARCHAR,
        max_length=36,
        # is_primary=True,
    )
    aadhaar = FieldSchema(
        name="aadhaar",
        dtype=DataType.VARCHAR,
        max_length=12,
    )
    name = FieldSchema(
        name="name",
        dtype=DataType.VARCHAR,
        max_length=256,
    )
    # Construct a schema with the predefined fields
    schema = CollectionSchema(
        fields=[primary_key, guid, vector, aadhaar, name],
        description="facial_embedding",
        auto_id=True,
    )

    client.create_collection(
        collection_name=collection_name,
        metric_type="IP",
        schema=schema,
        consistency_level="Strong"
    )
    client.create_index(
        collection_name=collection_name,
        index_params=index_params
    )
    logger.info(f'Face collection {collection_name} created successfully')


client = MilvusClient(uri=CLUSTER_ENDPOINT)
if not client.has_collection(collection_name=FACE_COLLECTION_NAME):
    create_collection(client, FACE_COLLECTION_NAME)

if not client.has_collection(collection_name=FACE_COLLECTION_BLACKLIST):
    create_collection(client, FACE_COLLECTION_BLACKLIST)

collection_default = Collection(name=FACE_COLLECTION_NAME)
collection_default.load()
collection_blacklist = Collection(name=FACE_COLLECTION_BLACKLIST)
collection_blacklist.load()
client.close()

# # index = faiss.IndexFlatL2(d)
# index = faiss.IndexFlatIP(d)
# # A dictionary to map face IDs to vector indices
# face_db = {}

def normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm

processing = None

app = FastAPIOffline(
    title="CensusCounters-REST",
    description="FastAPI wrapper for CensusCounters Face API.",
    version=__version__,
)


@app.on_event('startup')
async def startup():
    """
    Perform any necessary setup when the application starts up.
    This includes initializing the `processing` object aiohttp.ClientSession.

    Raises:
        Exception: If an error occurs during processing initialization.
    """
    logger.info(f"Starting processing module...")
    global processing
    try:
        timeout = ClientTimeout(total=60., )
        dl_client = aiohttp.ClientSession(timeout=timeout, connector=TCPConnector(verify_ssl=False))
        processing = Processing(det_name=settings.models.det_name, rec_name=settings.models.rec_name,
                                ga_name=settings.models.ga_name,
                                mask_detector=settings.models.mask_detector,
                                max_size=settings.models.max_size,
                                max_rec_batch_size=settings.models.rec_batch_size,
                                max_det_batch_size=settings.models.det_batch_size,
                                backend_name=settings.models.inference_backend,
                                force_fp16=settings.models.force_fp16,
                                triton_uri=settings.models.triton_uri,
                                root_dir='/models',
                                dl_client=dl_client
                                )
        logger.info(f"Processing module ready!")
    except Exception as e:
        logger.error(e)
        exit(1)


@app.post('/extract', tags=['Detection & recognition'])
async def extract(data: BodyExtract, accept: Optional[List[str]] = Header(None)):
    """
    Face extraction/embeddings endpoint accept json with
    parameters in following format:

       - **images**: dict containing either links or data lists. (*required*)
       - **threshold**: Detection threshold. Default: 0.6 (*optional*)
       - **embed_only**: Treat input images as face crops (112x112 crops required), omit detection step. Default: False (*optional*)
       - **return_face_data**: Return face crops encoded in base64. Default: False (*optional*)
       - **return_landmarks**: Return face landmarks. Default: False (*optional*)
       - **extract_embedding**: Extract face embeddings (otherwise only detect faces). Default: True (*optional*)
       - **extract_ga**: Extract gender/age. Default: False (*optional*)
       - **limit_faces**: Maximum number of faces to be processed.  0 for unlimited number. Default: 0 (*optional*)
       - **verbose_timings**: Return all timings. Default: False (*optional*)
       - **msgpack**: Serialize output to msgpack format for transfer. Default: False (*optional*)
       \f

       :return:
       List[List[dict]]
    """
    # try:
    images = jsonable_encoder(data.images)
    # print(images, flush=True)
    output = await processing.extract(images, max_size=data.max_size, return_face_data=data.return_face_data,
                                      embed_only=data.embed_only, extract_embedding=data.extract_embedding,
                                      threshold=data.threshold, extract_ga=data.extract_ga,
                                      limit_faces=data.limit_faces, min_face_size=data.min_face_size,
                                      return_landmarks=data.return_landmarks,
                                      detect_masks=data.detect_masks,
                                      verbose_timings=data.verbose_timings)

    if data.msgpack or 'application/x-msgpack' in accept:
        return PlainTextResponse(msgpack.dumps(output, use_single_float=True), media_type='application/x-msgpack')
    else:
        return UJSONResponse(output)
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=str(e))


@app.post("/delete")
async def delete(id: str, collection_name: str = Form("default"), conn=Depends(get_milvus_connection)):
    if collection_name not in [FACE_COLLECTION_NAME, FACE_COLLECTION_BLACKLIST]:
        raise HTTPException(status_code=400, detail="Invalid collection name.")

    collection = Collection(name=collection_name)
    expr = f'guid=="{id}"'
    collection.delete(expr=expr)
    logger.info(f'The face {id} has been wiped from "{collection_name}".')
    return {"status": "success", "guid": id, "collection": collection_name}


@app.post("/clean_database")
async def clean_database():
    client = MilvusClient(uri=CLUSTER_ENDPOINT)

    # Drop and recreate both collections
    logger.info("Cleaning all collections...")
    for name in [FACE_COLLECTION_NAME, FACE_COLLECTION_BLACKLIST]:
        if client.has_collection(collection_name=name):
            client.drop_collection(collection_name=name)
        create_collection(client, name)
        collection = Collection(name=name)
        collection.load()

    client.close()
    return {"status": "success", "detail": "All collections have been cleaned and recreated."}


@app.post("/list_all_faces")
async def list_all_faces(collection_name: str = Form("default"), conn=Depends(get_milvus_connection)):
    if collection_name not in [FACE_COLLECTION_NAME, FACE_COLLECTION_BLACKLIST]:
        raise HTTPException(status_code=400, detail="Invalid collection name.")

    collection = Collection(collection_name)
    results = collection.query(expr="guid != ''", output_fields=["guid", "name"])
    return {"status": "success", "collection": collection_name, "result": results}


@contextmanager
def timer(step_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{step_name} took {elapsed:.3f} seconds")


@app.post("/enroll")
async def enroll(
    id: str,
    file: UploadFile = File(...),
    name: str = Form(""),
    aadhaar: str = Form(""),
    #collection_name: str = Form("default"),
    collection_name: str = Form(""),
    conn=Depends(get_milvus_connection)
):
    # Validate the collection name
    if collection_name not in [FACE_COLLECTION_NAME, FACE_COLLECTION_BLACKLIST]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection name. Must be '{FACE_COLLECTION_NAME}' or '{FACE_COLLECTION_BLACKLIST}'.",
        )
    file_extension = file.filename.split(".")[-1]
    temp_file_path = f"test_images/{uuid.uuid4()}.{file_extension}"
    with open(temp_file_path, "wb") as temp_file:
        shutil.copyfileobj(file.file, temp_file)

    images = {"data": None, "urls": [temp_file_path]}
    with timer("extract_vector"):
        output = await processing.extract(images, max_size=[640, 640], return_face_data=False,
                                      embed_only=False, extract_embedding=True,
                                      threshold=0.6, extract_ga=False,
                                      limit_faces=0, min_face_size=0,
                                      return_landmarks=False,
                                      detect_masks=False,
                                      verbose_timings=False)
        if len(output['data'][0]['faces']) == 0:
            return {"status": "error", "guid": None, "name": None, "aadhaar": None}
        face_vector = np.array(output['data'][0]['faces'][0]['vec'])
        face_vector = normalize_vector(face_vector)

    with timer("insert_vector_to_db"):
        # Add vector to facial DB
        data = [{"guid": id, "vector": face_vector, "name": name, "aadhaar": aadhaar}]
        collection = Collection(name=collection_name)
        collection.insert(data=data)
    # with timer("reindex_db"):
        # collection.flush()

    # Clean up temporary file
    os.remove(temp_file_path)

    logger.info(f'A new face has been enrolled in "{collection_name}". Current face count in that collection is: {collection.num_entities}')

    # collection_stats = client.get_collection_stats(collection_name=FACE_COLLECTION_NAME)
    # if 'inMemory_percent' in collection_stats and collection_stats['inMemory_percent'] == 100:
    #     logger.info(f"The collection {FACE_COLLECTION_NAME} is fully loaded into memory.")
    # else:
    #     logger.info(f"The collection {FACE_COLLECTION_NAME} is not fully loaded into memory.")
    return {"status": "success", "guid": id, "name": name, "aadhaar": aadhaar, "collection": collection_name}


@app.post("/flush", tags=['Utility'])
async def flush_collection(collection_name: str = Form(...)):
    """
    Manually flushes a collection to ensure all inserted data is indexed and searchable.
    This is useful after batch enrollments.

    - **collection_name**: The name of the collection to flush (e.g., 'default', 'blacklist').
    """
    # 1. Validate the collection name
    if collection_name not in [FACE_COLLECTION_NAME, FACE_COLLECTION_BLACKLIST]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection name. Must be '{FACE_COLLECTION_NAME}' or '{FACE_COLLECTION_BLACKLIST}'.",
        )

    try:
        target_collection = Collection(name=collection_name)

        # 2. Get the entity count *before* flushing
        entities_before = target_collection.num_entities

        # 3. Perform the flush operation
        logger.info(f"Flushing collection '{collection_name}'...")
        target_collection.flush()

        # 4. Get the entity count *after* flushing
        entities_after = target_collection.num_entities

        logger.info(
            f"Flush complete for '{collection_name}'. Entity count changed from {entities_before} to {entities_after}.")

        return {
            "status": "success",
            "collection": collection_name,
            "entities_before": entities_before,
            "entities_after": entities_after
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def search_in_collection(collection_name: str, vector: list):
    """
    Performs a search for a given vector in a specified Milvus collection.
    """
    logger.info(f'Searching in "{collection_name}"...')
    collection = Collection(name=collection_name)
    matches = collection.search(
        data=[vector],
        anns_field='vector',
        limit=5,
        param={"metric_type": "IP"},
        output_fields=["guid", "name", "aadhaar"],
    )
    processed_matches = search_result_to_dict(matches)
    for hit in processed_matches:
        hit['similarity'] = (hit['distance'] + 1) / 2
    return processed_matches

@app.post("/recognize")
async def recognize(file: UploadFile = File(...), conn=Depends(get_milvus_connection)):
    # try:
    # Save the uploaded file to a temporary location
    file_extension = file.filename.split(".")[-1]
    temp_file_path = f"test_images/{uuid.uuid4()}.{file_extension}"
    with open(temp_file_path, "wb") as temp_file:
        shutil.copyfileobj(file.file, temp_file)

    # Extract face vector
    images = {"data": None, "urls": [temp_file_path]}
    # logger.info(images)
    output = await processing.extract(images, max_size=[640, 640], return_face_data=False,
                                      embed_only=False, extract_embedding=True,
                                      threshold=0.6, extract_ga=False,
                                      limit_faces=0, min_face_size=0,
                                      return_landmarks=False,
                                      detect_masks=False,
                                      verbose_timings=False)
    # logger.info(output)
    if len(output['data'][0]['faces']) == 0:
        return {"status": "error", "guid": None, "name": None, "aadhaar": None, 'matches': []}

    face_vector = np.array(output['data'][0]['faces'][0]['vec'])
    # face_vector = face_vector.reshape(1, -1)
    face_vector = normalize_vector(face_vector)

    matches_default, matches_blacklist = await asyncio.gather(
        search_in_collection(FACE_COLLECTION_NAME, face_vector),
        search_in_collection(FACE_COLLECTION_BLACKLIST, face_vector)
    )

    # Clean up temporary file
    os.remove(temp_file_path)

    # Prepare the JSON response
    response = {
        "status": "success",
        "matches": matches_default,
        "matches_blacklist": matches_blacklist
    }

    return response
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=str(e))

@app.post('/draw_detections', tags=['Detection & recognition'])
async def draw(data: BodyDraw):
    """
    Return image with drawn faces for testing purposes.

       - **images**: dict containing either links or data lists. (*required*)
       - **threshold**: Detection threshold. Default: 0.6 (*optional*)
       - **draw_landmarks**: Draw faces landmarks Default: True (*optional*)
       - **draw_scores**: Draw detection scores Default: True (*optional*)
       - **draw_sizes**: Draw face sizes Default: True (*optional*)
       - **limit_faces**: Maximum number of faces to be processed.  0 for unlimited number. Default: 0 (*optional*)
       \f
    """
    try:
        images = jsonable_encoder(data.images)
        output = await processing.draw(images, threshold=data.threshold,
                                       draw_landmarks=data.draw_landmarks, draw_scores=data.draw_scores,
                                       limit_faces=data.limit_faces, min_face_size=data.min_face_size,
                                       draw_sizes=data.draw_sizes,
                                       detect_masks=data.detect_masks)
        output.seek(0)
        return StreamingResponse(output, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/multipart/draw_detections', tags=['Detection & recognition'])
async def draw_upl(file: bytes = File(...), threshold: float = Form(0.6), draw_landmarks: bool = Form(True),
                   draw_scores: bool = Form(True), draw_sizes: bool = Form(True), limit_faces: int = Form(0), use_rotation: bool = Form(False)):
    """
    Return image with drawn faces for testing purposes.

       - **file**: Image file (*required*)
       - **threshold**: Detection threshold. Default: 0.6 (*optional*)
       - **draw_landmarks**: Draw faces landmarks Default: True (*optional*)
       - **draw_scores**: Draw detection scores Default: True (*optional*)
       - **draw_sizes**: Draw face sizes Default: True (*optional*)
       - **limit_faces**: Maximum number of faces to be processed.  0 for unlimited number. Default: 0 (*optional*)
       \f
    """
    try:
        output = await processing.draw(file, threshold=threshold,
                                       draw_landmarks=draw_landmarks, draw_scores=draw_scores, draw_sizes=draw_sizes,
                                       limit_faces=limit_faces,
                                       multipart=True)
        output.seek(0)
        return StreamingResponse(output, media_type='image/jpg')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/info', tags=['Utility'])
def info():
    """
    Enlist container configuration.

    """
    try:
        about = dict(
            version=__version__,
            tensorrt_version=os.getenv('TRT_VERSION', os.getenv('TENSORRT_VERSION')),
            log_level=settings.log_level,
            models=settings.models.dict(),
            defaults=settings.defaults.dict(),
        )
        about['models'].pop('ga_ignore', None)
        about['models'].pop('rec_ignore', None)
        about['models'].pop('mask_ignore', None)
        about['models'].pop('device', None)
        return about
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/', include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")


@app.post("/validate/image_quality_check", tags=["Validation"])
async def check_image_quality(file: UploadFile = File(...)):
    """
    Validate an image for enrollment:
    - Exactly ONE face must be present
    - No enrollment or DB interaction

    Returns:
    {
        status: "accept" | "reject",
        reason: str,
        face_count: int
    }
    """

    # 1. Save uploaded image temporarily
    file_extension = file.filename.split(".")[-1]
    temp_file_path = f"/tmp/{uuid.uuid4()}.{file_extension}"

    try:
        with open(temp_file_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
        blur_score = compute_blur_score(temp_file_path)
        print(f'blur_score: {blur_score}, threshold: {BLUR_THRESHOLD}')

        if blur_score < BLUR_THRESHOLD:
            return {
                "status": "reject",
                "reason": "Image is too blurry. Try again.",
                "blur_score": round(blur_score, 2),
                "threshold": BLUR_THRESHOLD
            }


        # 2. Prepare input for processing.extract
        images = {
            "data": None,
            "urls": [temp_file_path]
        }

        # 3. Run face detection only (no embeddings)
        output = await processing.extract(
            images=images,
            max_size=[640, 640],
            embed_only=False,
            extract_embedding=False,   # IMPORTANT: detection only
            extract_ga=False,
            return_face_data=True,
            threshold=0.6,
            limit_faces=0,
            min_face_size=0,
            return_landmarks=False,
            detect_masks=True,
            verbose_timings=False
        )

        faces = output["data"][0]["faces"]

        #4.Check Faces
        face_count = len(faces)
        if face_count == 0:
            return {
                "status": "reject",
                "reason": "No face detected in the image. Please upload an image with just 1 face.",
                "face_count": 0
            }

        if face_count > 1:
            return {
                "status": "reject",
                "reason": "Multiple faces detected in the image. Please upload an image with just 1 face.",
                "face_count": face_count
            }

        # 5.Check Mask
        face = faces[0]
        import pprint
        pprint.pprint(face)
        #mask_info = face.get("mask_detected", face.get("mask", False))

        mask_info = (
                face.get("mask_detected") is True
                or face.get("mask") is True
                or face.get("attributes", {}).get("mask") is True
                or face.get("attributes", {}).get("mask_detected") is True
        )

        if mask_info is True:
            return {
                "status": "reject",
                "reason": "Face mask detected. Please upload an image without a mask."
            }

        # 6. Accept validation passed
        return {
            "status": "accept",
            "reason": "Image quality checks passed.",
            "face_count": face_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 7. Cleanup
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


BLUR_THRESHOLD = 10.0 #120.0  # Tune this based on real data

def compute_blur_score(image_path: str) -> float:
    """
    Computes blur score using Laplacian variance.
    Higher value = sharper image.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Unable to read image")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    score = cv2.Laplacian(gray, cv2.CV_64F).var()
    return float(score)