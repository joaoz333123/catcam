import os
import sys
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import json

# Setup imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import init_db, get_visits, delete_visit
from backend.detector import detector, CONFIG_PATH, RECORDINGS_DIR

# Inicializa banco de dados
init_db()

app = FastAPI(title="CatCam Monitor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
os.makedirs(FRONTEND_DIR, exist_ok=True)

class ROIUpdateRequest(BaseModel):
    polygon: Optional[List[List[float]]] = None
    confidence_threshold: Optional[float] = None
    debounce_seconds: Optional[int] = None
    target_fps: Optional[int] = None
    target_mode: Optional[str] = None
    color_filter: Optional[str] = None

@app.on_event("startup")
def startup_event():
    detector.start()
    print("[Server] Detector iniciado no startup do FastAPI.")

@app.on_event("shutdown")
def shutdown_event():
    detector.stop()
    print("[Server] Detector parado no shutdown do FastAPI.")

@app.get("/api/status")
def get_status():
    visits_today = get_visits(filter_range="today", limit=100)
    total_today = len(visits_today)
    avg_duration = round(sum(v["duration_seconds"] for v in visits_today) / total_today) if total_today > 0 else 0

    return {
        "telemetry": detector.status,
        "metrics": {
            "total_visits_today": total_today,
            "avg_duration_today_seconds": avg_duration
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
            color_filter=payload.color_filter
        )
        return {"status": "success", "message": "Configurações atualizadas com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/feed/annotated")
def stream_annotated():
    def frame_generator():
        last_jpeg = None
        while True:
            jpeg = detector.get_annotated_jpeg()
            if jpeg is not None and jpeg != last_jpeg:
                last_jpeg = jpeg
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            import time
            time.sleep(0.03) # Verifica a ~30 Hz e envia quadros na velocidade real do detector

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/recordings/{filename}")
def get_recording(filename: str):
    filepath = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Arquivo de gravação não encontrado.")
    return FileResponse(filepath, media_type="video/mp4")

# Servir Frontend
@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>CatCam Frontend ainda não criado.</h1>"

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
