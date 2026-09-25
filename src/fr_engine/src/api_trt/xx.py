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

        if blur_score < BLUR_THRESHOLD:
            return {
                "status": "reject",
                "reason": "Image is too blurry",
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
            return_face_data=False,
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
                "reason": "NO_FACE_DETECTED",
                "face_count": 0
            }

        if face_count > 1:
            return {
                "status": "reject",
                "reason": "MULTIPLE_FACES_DETECTED",
                "face_count": face_count
            }

        # 5.Check Mask
        face = faces[0]
        mask_info = face.get("mask_detected", face.get("mask", False))

        if mask_info is True:
            return {
                "status": "reject",
                "reason": "Face mask detected. Please upload an image without a mask."
            }

        # 6. Accept validation passed
        return {
            "status": "accept",
            "reason": "Image quality checks passed"
            "face_count": face_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 7. Cleanup
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/validate/detect_mask", tags=["Validation"])
async def detect_mask(file: UploadFile = File(...)):
    """
    Detect whether a face is wearing a mask.
    Assumes the image contains exactly one face.
    """
    try:
        image_bytes = await file.read()

        images = {
            "image": [{
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }]
        }

        result = await processing.extract(
            images=images,
            extract_embedding=False,
            extract_ga=False,
            detect_masks=True,
            limit_faces=1
        )

        faces = result.get("faces", [])
        if not faces:
            return {
                "status": "reject",
                "reason": "No face detected"
            }

        face = faces[0]

        # Common fields you’ll see depending on model
        mask_info = face.get("mask") or face.get("mask_detected")

        if mask_info is True:
            return {
                "status": "reject",
                "reason": "Face mask detected. Please upload an image without a mask."
            }

        return {
            "status": "accept",
            "reason": "No mask detected"
        }

    except Exception as e:
        return {
            "status": "reject",
            "reason": f"Mask detection failed: {str(e)}"
        }

BLUR_THRESHOLD = 120.0  # Tune this based on real data

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

@app.post("/validate/detect_blur", tags=["Validation"])
async def detect_blur(file: UploadFile = File(...)):
    """
    Validates whether an image is too blurry for face enrollment.

    Returns:
    {
        "status": "accept" | "reject",
        "blur_score": float,
        "reason": str (optional)
    }
    """

    # Save temp image
    ext = file.filename.split(".")[-1]
    temp_path = f"/tmp/{uuid.uuid4()}.{ext}"

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        blur_score = compute_blur_score(temp_path)

        if blur_score < BLUR_THRESHOLD:
            return {
                "status": "reject",
                "reason": "Image is too blurry",
                "blur_score": round(blur_score, 2),
                "threshold": BLUR_THRESHOLD
            }

        return {
            "status": "accept",
            "blur_score": round(blur_score, 2),
            "threshold": BLUR_THRESHOLD
        }

    except Exception as e:
        logger.error(f"Blur detection failed: {e}")
        raise HTTPException(status_code=500, detail="Blur detection failed")

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

------------------

def validate_enrollment_image(files):
    """
    Runs all face validation checks required before enrollment.

    Returns:
        {
            "status": "accept" | "reject",
            "reason": "human readable message"
        }

    Current checks:
    1. Exactly one face must be detected
    2. There is no mask on the face
    """

    try:
        service = app.config.get("FACE_RECOGNITION_SERVICE")
        if not service:
            return {
                "status": "reject",
                "reason": "Validation service not configured"
            }

        # 1. Face check
        files["file"][1].seek(0)
        url = service + "validate/detect_faces"
        response = requests.post(url, files=files, timeout=5)
        result = response.json()

        if result.get("status") != "accept":
            return {
                "status": "reject",
                "reason": result.get("reason", "Face validation failed")
            }

        # 2. Mask check
        files["file"][1].seek(0)
        url = service + "validate/detect_mask"
        response = requests.post(url, files=files, timeout=5)
        result = response.json()

        if result.get("status") != "accept":
            return {
                "status": "reject",
                "reason": result.get("reason", "Mask validation failed")
            }

        # 3. Blur check
        files["file"][1].seek(0)
        url = service + "validate/detect_blur"
        response = requests.post(url, files=files, timeout=5)
        result = response.json()

        if result.get("status") != "accept":
            return {
                "status": "reject",
                "reason": result.get("reason", "Image is too blurry")
            }

        return {
            "status": "accept",
            "reason": "Image validation passed"
        }

    except Exception as e:
        print("Validation service error:", e, flush=True)
        return {
            "status": "reject",
            "reason": "Image validation service unavailable"
        }
