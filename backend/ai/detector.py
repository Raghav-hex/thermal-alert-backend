import os
import numpy as np
import cv2

DETECTION_STATUS: dict[int, dict] = {}


def _fire_mask(hsv):
    lower1 = np.array([0, 100, 100], dtype=np.uint8)
    upper1 = np.array([10, 255, 255], dtype=np.uint8)
    lower2 = np.array([170, 100, 100], dtype=np.uint8)
    upper2 = np.array([180, 255, 255], dtype=np.uint8)
    m1 = cv2.inRange(hsv, lower1, upper1)
    m2 = cv2.inRange(hsv, lower2, upper2)
    return cv2.bitwise_or(m1, m2)


def _smoke_mask(hsv):
    lower = np.array([0, 0, 50], dtype=np.uint8)
    upper = np.array([180, 30, 220], dtype=np.uint8)
    return cv2.inRange(hsv, lower, upper)


def analyze_frame(factory_id: int, frame_bytes: bytes):
    try:
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]
        total = h * w
        fire_px = cv2.countNonZero(_fire_mask(hsv))
        smoke_px = cv2.countNonZero(_smoke_mask(hsv))
        fire_conf = min(1.0, fire_px / (total * 0.15))
        smoke_conf = min(1.0, smoke_px / (total * 0.20))
        FIRE_TH = 0.25
        SMOKE_TH = 0.20
        DETECTION_STATUS[factory_id] = {
            "fire_detected": fire_conf >= FIRE_TH,
            "smoke_detected": smoke_conf >= SMOKE_TH,
            "fire_confidence": round(fire_conf, 3),
            "smoke_confidence": round(smoke_conf, 3),
        }
    except Exception:
        pass


def get_status(factory_id: int) -> dict | None:
    return DETECTION_STATUS.get(factory_id)


def get_all_status() -> dict:
    return {str(k): v for k, v in DETECTION_STATUS.items()}
