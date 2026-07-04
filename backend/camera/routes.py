import struct
import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse, StreamingResponse
from jose import jwt, JWTError
from config import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/camera", tags=["camera"])

camera_frames: dict[int, bytes] = {}
camera_last_upload: dict[int, float] = {}
camera_frame_counter: dict[int, int] = {}
STALE_AFTER = 30
MJPEG_BOUNDARY = "frame"
admin_connections: list[WebSocket] = []


def _decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


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
                camera_last_upload[factory_id] = time.time()
                camera_frame_counter[factory_id] = camera_frame_counter.get(factory_id, 0) + 1
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
            camera_last_upload.pop(factory_id, None)

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
    camera_last_upload[factory_id] = time.time()
    camera_frame_counter[factory_id] = camera_frame_counter.get(factory_id, 0) + 1
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
    last = camera_last_upload.get(factory_id)
    if not last or time.time() - last > STALE_AFTER:
        return Response(status_code=204)
    return Response(content=frame, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})


@router.get("/mjpeg/{factory_id}")
async def mjpeg_stream(factory_id: int):
    frame = camera_frames.get(factory_id)
    last_upload = camera_last_upload.get(factory_id)
    if not frame:
        return Response(status_code=404)
    if not last_upload or time.time() - last_upload > STALE_AFTER:
        return Response(status_code=204)

    boundary = MJPEG_BOUNDARY

    async def generate():
        last_count = 0
        while True:
            current_count = camera_frame_counter.get(factory_id, 0)
            current_frame = camera_frames.get(factory_id)
            current_upload = camera_last_upload.get(factory_id)
            if not current_frame or not current_upload or time.time() - current_upload > STALE_AFTER:
                break
            if current_count != last_count:
                last_count = current_count
                yield f"--{boundary}\r\nContent-Type: image/jpeg\r\n\r\n".encode()
                yield current_frame
                yield b"\r\n"
            await asyncio.sleep(0.033)

    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/latest")
async def get_all_frames():
    result = {}
    for fid, frame in camera_frames.items():
        import base64
        result[str(fid)] = base64.b64encode(frame).decode()
    return result


@router.get("/debug")
async def camera_debug():
    return {
        "active_factories": list(camera_frames.keys()),
        "frame_sizes": {str(fid): len(frame) for fid, frame in camera_frames.items()},
        "frame_counts": {str(fid): camera_frame_counter.get(fid, 0) for fid in camera_frames},
        "admin_count": len(admin_connections),
    }
