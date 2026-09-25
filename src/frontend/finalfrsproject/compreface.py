from compreface import CompreFace
from compreface.service import RecognitionService, DetectionService
from compreface.collections import FaceCollection
from compreface.collections.face_collections import Subjects



DOMAIN: str = 'http://localhost'
PORT: str = '8000'
RECOGNITION_API_KEY: str = '675b5153-3a80-45af-96b0-bb2c04337c64'
DETECTION_API_KEY: str = 'd7fd233d-ded8-42a1-8f65-ed3e8114cba1'
#COMPREFACE_SERVICE_TOKEN = '371efb8f-2b35-44cd-9361-d27cc6619e60'


#compre_face: CompreFace = CompreFace(DOMAIN, PORT, {
#	"face_plugins": "age,gender"
#})

compre_face: CompreFace = CompreFace(DOMAIN, PORT, {})

recognition: RecognitionService = compre_face.init_face_recognition(RECOGNITION_API_KEY)

detection: DetectionService = compre_face.init_face_detection(DETECTION_API_KEY)

face_collection: FaceCollection = recognition.get_face_collection()

subjects: Subjects = recognition.get_subjects()

