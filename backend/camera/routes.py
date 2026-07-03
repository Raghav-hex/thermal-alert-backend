import struct
import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse
from jose import jwt, JWTError
from config import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/camera", tags=["camera"])

camera_frames: dict[int, bytes] = {}
admin_connections: list[WebSocket] = []
_detection_status: dict[int, dict] = {}
_executor = ThreadPoolExecutor(max_workers=1)


def _decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def _analyze_frame(factory_id: int, frame_bytes: bytes):
    try:
        from PIL import Image
        import numpy as np
        pil = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
        arr = np.array(pil)
        h, w = arr.shape[:2]
        total = h * w

        r, g, b = arr[:, :, 0].astype(np.float64), arr[:, :, 1].astype(np.float64), arr[:, :, 2].astype(np.float64)
        intensity = (r + g + b) / 3.0

        fire_mask = (r > 180) & (r > g * 1.4) & (r > b * 1.4) & (r > 100)
        fire_px = int(np.sum(fire_mask))

        smoke_mask = (intensity > 80) & (intensity < 220) & (np.abs(r - g) < 30) & (np.abs(g - b) < 30) & (np.abs(r - b) < 30)
        smoke_px = int(np.sum(smoke_mask))

        fire_conf = min(1.0, fire_px / (total * 0.12))
        smoke_conf = min(1.0, smoke_px / (total * 0.18))
        _detection_status[factory_id] = {
            "fire_detected": fire_conf >= 0.25,
            "smoke_detected": smoke_conf >= 0.20,
            "fire_confidence": round(fire_conf, 3),
            "smoke_confidence": round(smoke_conf, 3),
        }
    except Exception:
        pass


async def _run_ai(factory_id: int, frame_bytes: bytes):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _analyze_frame, factory_id, frame_bytes)


@router.websocket("/stream/{factory_id}")
async def camera_stream(websocket: WebSocket, factory_id: int):
    token = websocket.query_params.get("token", "")
    payload = _decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    role = payload.get("role", "")
    token_factory_id = payload.get("factory_id")

    if role == "factory":
        if token_factory_id != factory_id:
            await websocket.close(code=4003, reason="Factory ID mismatch")
            return
        await websocket.accept()
        header = struct.pack("!I", factory_id)
        try:
            while True:
                data = await websocket.receive_bytes()
                camera_frames[factory_id] = data
                asyncio.ensure_future(_run_ai(factory_id, data))
                framed = header + data
                dead = []
                for ws in admin_connections:
                    try:
                        await ws.send_bytes(framed)
                    except Exception:
                        dead.append(ws)
                for d in dead:
                    admin_connections.remove(d)
        except WebSocketDisconnect:
            pass
        finally:
            camera_frames.pop(factory_id, None)

    elif role == "admin":
        await websocket.accept()
        admin_connections.append(websocket)
        for fid, frame in camera_frames.items():
            try:
                await websocket.send_bytes(struct.pack("!I", fid) + frame)
            except Exception:
                break
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in admin_connections:
                admin_connections.remove(websocket)
    else:
        await websocket.close(code=4001, reason="Unknown role")


@router.post("/upload/{factory_id}")
async def upload_frame(factory_id: int, token: str, request: Request):
    decoded = _decode_token(token)
    if not decoded or decoded.get("role") != "factory" or decoded.get("factory_id") != factory_id:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.body()
    camera_frames[factory_id] = body
    asyncio.ensure_future(_run_ai(factory_id, body))
    header = struct.pack("!I", factory_id)
    framed = header + body
    dead = []
    for ws in admin_connections:
        try:
            await ws.send_bytes(framed)
        except Exception:
            dead.append(ws)
    for d in dead:
        admin_connections.remove(d)
    return {"ok": True}


@router.get("/latest/{factory_id}")
async def get_latest_frame(factory_id: int):
    frame = camera_frames.get(factory_id)
    if not frame:
        return Response(status_code=404)
    return Response(content=frame, media_type="image/jpeg")


@router.get("/latest")
async def get_all_frames():
    result = {}
    for fid, frame in camera_frames.items():
        import base64
        result[str(fid)] = base64.b64encode(frame).decode()
    return result


@router.get("/detection/{factory_id}")
async def camera_detection(factory_id: int):
    s = _detection_status.get(factory_id)
    if not s:
        return {"fire_detected": False, "smoke_detected": False, "fire_confidence": 0, "smoke_confidence": 0}
    return s


@router.get("/detection")
async def camera_detection_all():
    return {str(k): v for k, v in _detection_status.items()}


@router.get("/debug")
async def camera_debug():
    return {
        "active_factories": list(camera_frames.keys()),
        "frame_sizes": {str(fid): len(frame) for fid, frame in camera_frames.items()},
        "admin_count": len(admin_connections),
    }
