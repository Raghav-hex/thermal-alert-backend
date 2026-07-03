import struct
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response, JSONResponse
from jose import jwt, JWTError
from config import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/camera", tags=["camera"])

camera_frames: dict[int, bytes] = {}
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


@router.get("/debug")
async def camera_debug():
    import sys
    return {
        "active_factories": list(camera_frames.keys()),
        "frame_sizes": {str(fid): len(frame) for fid, frame in camera_frames.items()},
        "admin_count": len(admin_connections),
    }
