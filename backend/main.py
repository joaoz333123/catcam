import os
import sys

# Otimização crítica de CPU: instrui o runtime OpenMP/oneTBB da Intel a suspender threads imediatamente
# após a inferência (blocktime=0 e wait policy=passive), eliminando 100% do spin-wait (queimava 600% de CPU à toa)
os.environ["KMP_BLOCKTIME"] = "0"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

import asyncio
import json
import httpx
import websockets
from starlette.background import BackgroundTask
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional

# Setup imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import init_db, get_visits, delete_visit, get_visits_breakdown
from backend.detector import detector, CONFIG_PATH, RECORDINGS_DIR, send_ntfy_notification_async

# Inicializa banco de dados
init_db()

app = FastAPI(title="CatCam Monitor API", version="2.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Cliente HTTP assíncrono para o Proxy Reverso do go2rtc (Porta 1984)
go2rtc_client = httpx.AsyncClient(base_url="http://127.0.0.1:1984", timeout=60.0)

class ROIUpdateRequest(BaseModel):
    polygon: Optional[List[List[float]]] = None
    confidence_threshold: Optional[float] = None
    debounce_seconds: Optional[int] = None
    target_fps: Optional[int] = None
    target_mode: Optional[str] = None
    color_filter: Optional[str] = None
    target_cats: Optional[List[str]] = None
    target_presets: Optional[List[str]] = None
    extra_classes: Optional[List[int]] = None
    notifications_enabled: Optional[bool] = None
    ntfy_enabled: Optional[bool] = None
    ntfy_topic: Optional[str] = None
    ntfy_server: Optional[str] = None
    public_url: Optional[str] = None

class NtfyTestRequest(BaseModel):
    topic: str
    server: Optional[str] = "https://ntfy.sh"
    public_url: Optional[str] = ""

@app.on_event("startup")
def startup_event():
    detector.start()
    print("[Server] Detector e Gateway iniciados no startup do FastAPI.")

@app.on_event("shutdown")
async def shutdown_event():
    detector.stop()
    await go2rtc_client.aclose()
    print("[Server] Detector e cliente HTTP parados no shutdown do FastAPI.")

# ==========================================================
# PROXY REVERSO GO2RTC (UNIFICAÇÃO DE PORTAS WEBRTC / HTTP / WS)
# ==========================================================

@app.websocket("/go2rtc/api/ws")
async def websocket_go2rtc_proxy(client_ws: WebSocket):
    """
    Ponte WebSocket bidirecional para o go2rtc:
    Permite que conexões WebRTC e streams MSE funcionem transparentemente através da porta 8000
    e através de túneis HTTPS/WSS (Cloudflare Tunnel).
    """
    await client_ws.accept()
    query = client_ws.scope.get("query_string", b"").decode("utf-8")
    target_url = "ws://127.0.0.1:1984/api/ws"
    if query:
        target_url += f"?{query}"

    try:
        async with websockets.connect(target_url, max_size=16 * 1024 * 1024) as server_ws:
            async def client_to_server():
                try:
                    while True:
                        msg = await client_ws.receive()
                        if "text" in msg:
                            await server_ws.send(msg["text"])
                        elif "bytes" in msg:
                            await server_ws.send(msg["bytes"])
                        elif msg.get("type") == "websocket.disconnect":
                            break
                except Exception:
                    pass

            async def server_to_client():
                try:
                    async for msg in server_ws:
                        if isinstance(msg, str):
                            await client_ws.send_text(msg)
                        else:
                            await client_ws.send_bytes(msg)
                except Exception:
                    pass

            await asyncio.gather(client_to_server(), server_to_client(), return_exceptions=True)
    except Exception as e:
        print(f"[Proxy] WebSocket go2rtc ponte finalizada: {e}")
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass

@app.api_route("/go2rtc/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
async def go2rtc_http_proxy(path: str, request: Request):
    """
    Proxy Reverso HTTP transparente para arquivos estáticos e API do go2rtc (stream.html, video-rtc.js, etc.)
    """
    url = f"/{path}"
    query = request.url.query
    if query:
        url += f"?{query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    try:
        req = go2rtc_client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=body
        )
        resp = await go2rtc_client.send(req, stream=True)

        resp_headers = {
            k: v for k, v in resp.headers.items() 
            if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
        }

        return StreamingResponse(
            resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=resp_headers,
            background=BackgroundTask(resp.aclose)
        )
    except Exception as e:
        return Response(f"Erro no gateway de vídeo local: {e}", status_code=502)

# ==========================================================
# ENDPOINTS DA API CATCAM
# ==========================================================

@app.get("/api/status")
def get_status():
    visits_today = get_visits(filter_range="today", limit=100)
    total_today = len(visits_today)
    avg_duration = round(sum(v["duration_seconds"] for v in visits_today) / total_today) if total_today > 0 else 0
    breakdown = get_visits_breakdown(filter_range="today")

    return {
        "telemetry": detector.status,
        "metrics": {
            "total_visits_today": total_today,
            "avg_duration_today_seconds": avg_duration,
            "breakdown": breakdown
        }
    }

@app.get("/api/visits")
def list_visits(range: Optional[str] = None, limit: int = 50):
    return get_visits(filter_range=range, limit=limit)

@app.delete("/api/visits/{visit_id}")
def remove_visit(visit_id: int):
    success = delete_visit(visit_id)
    if not success:
        raise HTTPException(status_code=404, detail="Visita não encontrada.")
    return {"status": "success", "deleted_id": visit_id}

@app.get("/api/roi")
def get_roi():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/roi")
def update_roi(payload: ROIUpdateRequest):
    try:
        detector.save_roi_config(
            polygon=payload.polygon,
            confidence=payload.confidence_threshold,
            debounce=payload.debounce_seconds,
            target_fps=payload.target_fps,
            target_mode=payload.target_mode,
            color_filter=payload.color_filter,
            target_cats=payload.target_cats,
            target_presets=payload.target_presets,
            extra_classes=payload.extra_classes,
            notifications_enabled=payload.notifications_enabled,
            ntfy_enabled=payload.ntfy_enabled,
            ntfy_topic=payload.ntfy_topic,
            ntfy_server=payload.ntfy_server,
            public_url=payload.public_url
        )
        return {"status": "success", "message": "Configurações atualizadas com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notifications/test-ntfy")
def test_ntfy_notification(payload: NtfyTestRequest):
    if not payload.topic or not payload.topic.strip():
        raise HTTPException(status_code=400, detail="O tópico do ntfy é obrigatório.")
    
    snapshot = detector.get_annotated_jpeg()
    send_ntfy_notification_async(
        title="🔔 CatCam AI • Teste de Notificação",
        msg="Seu celular está configurado e pronto para receber alertas do CatCam em tempo real!",
        image_bytes=snapshot,
        topic=payload.topic,
        server=payload.server or "https://ntfy.sh",
        click_url=payload.public_url or "http://localhost:8000"
    )
    return {"status": "success", "message": f"Notificação de teste enviada para o tópico '{payload.topic}'!"}

@app.get("/api/detections")
def get_detections():
    return detector.get_latest_ai_payload()

@app.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    await websocket.accept()
    last_ts = 0.0
    try:
        while True:
            payload = detector.get_latest_ai_payload()
            ts = payload.get("ts", 0.0)
            if ts != last_ts:
                last_ts = ts
                await websocket.send_json(payload)
            await asyncio.sleep(0.033)
    except (WebSocketDisconnect, Exception):
        pass

@app.get("/api/feed/annotated")
def stream_annotated():
    return StreamingResponse(
        detector.generate_smooth_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.api_route("/api/recordings/{filename}", methods=["GET", "HEAD"])
def get_recording(filename: str):
    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Arquivo de gravação não encontrado.")
    return FileResponse(
        filepath,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )

# Servir Frontend
@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>CatCam Frontend ainda não criado.</h1>"

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
