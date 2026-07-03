import os
import numpy as np
import cv2
from ultralytics import YOLO

_DIR = os.path.dirname(__file__)
_MODEL_CANDIDATES = [
    os.path.join(_DIR, "best.pt"),
    os.path.join(_DIR, "..", "..", "Fire_Smoke_Detection_Inference-main", "best.pt"),
    os.path.join(os.getcwd(), "Fire_Smoke_Detection_Inference-main", "best.pt"),
]
MODEL_PATH = None
for p in _MODEL_CANDIDATES:
    if os.path.exists(p):
        MODEL_PATH = p
        break

_model = None


def _load_model():
    global _model
    if _model is None:
        if MODEL_PATH is None:
            raise RuntimeError("best.pt not found in any candidate path")
        _model = YOLO(MODEL_PATH)
    return _model


CLASS_NAMES = {0: "FIRE", 1: "SMOKE"}
DETECTION_STATUS: dict[int, dict] = {}


def analyze_frame(factory_id: int, frame_bytes: bytes):
    try:
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        model = _load_model()
        results = model(img_rgb, verbose=False)[0]
        fire_conf = 0.0
        smoke_conf = 0.0
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            if cls_id == 0:
                fire_conf = max(fire_conf, conf)
            elif cls_id == 1:
                smoke_conf = max(smoke_conf, conf)
        THRESHOLD = 0.3
        DETECTION_STATUS[factory_id] = {
            "fire_detected": fire_conf >= THRESHOLD,
            "smoke_detected": smoke_conf >= THRESHOLD,
            "fire_confidence": round(fire_conf, 3),
            "smoke_confidence": round(smoke_conf, 3),
        }
    except Exception:
        pass


def get_status(factory_id: int) -> dict | None:
    return DETECTION_STATUS.get(factory_id)


def get_all_status() -> dict:
    return {str(k): v for k, v in DETECTION_STATUS.items()}
