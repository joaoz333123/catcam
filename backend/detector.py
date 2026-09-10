import os
import sys
import json
import time
import threading
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List

import supervision as sv
from ultralytics import YOLO

# Import local database helper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import record_visit, get_visits

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "roi_config.json"))
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "yolo11n_openvino_model"))
RECORDINGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "recordings"))
RTSP_URL = "rtsp://localhost:8554/cat_cam"

os.makedirs(RECORDINGS_DIR, exist_ok=True)

class FreshFrameReader(threading.Thread):
    """
    Thread dedicada para ler o stream RTSP continuamente e descartar o buffer atrasado.
    Garante latência zero no detector.
    """
    def __init__(self, rtsp_url: str):
        super().__init__(daemon=True)
        self.rtsp_url = rtsp_url
        self.latest_frame = None
        self.running = True
        self.connected = False
        self.lock = threading.Lock()
        self.new_frame_event = threading.Event()

    def run(self):
        while self.running:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not cap.isOpened():
                self.connected = False
                time.sleep(2)
                continue
                
            self.connected = True
            while self.running and cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                with self.lock:
                    self.latest_frame = frame
                    self.new_frame_event.set()
                    
            self.connected = False
            cap.release()
            time.sleep(1)

    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None

    def stop(self):
        self.running = False


class CatCamDetector:
    def __init__(self, rtsp_url: str = RTSP_URL):
        self.rtsp_url = rtsp_url
        self.reader = FreshFrameReader(rtsp_url)
        self.model = None
        self.zone = None
        self.zone_annotator = None
        self.box_annotator = sv.BoxAnnotator(thickness=2)
        self.label_annotator = sv.LabelAnnotator(text_scale=0.5)
        self.trace_annotator = sv.TraceAnnotator(thickness=2)
        self.tracker = sv.ByteTrack()
        
        self.polygon_normalized = []
        self.confidence_threshold = 0.45
        self.debounce_seconds = 5
        self.current_frame_shape = None
        
        # Estado de visita
        self.is_visiting = False
        self.visit_start_time = None
        self.last_seen_inside_time = 0
        self.current_video_writer = None
        self.current_video_filename = None
        
        # Telemetria ao vivo
        self.status: Dict[str, Any] = {
            "camera_online": False,
            "cat_detected": False,
            "cat_in_litterbox": False,
            "is_visiting": False,
            "visit_duration": 0,
            "last_event_time": None,
            "fps": 0.0,
            "inference_ms": 0.0
        }
        
        self.latest_annotated_jpeg: Optional[bytes] = None
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        self.load_roi_config()

    def load_roi_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.polygon_normalized = data.get("polygon", [[0.2, 0.3], [0.8, 0.3], [0.8, 0.85], [0.2, 0.85]])
                    self.confidence_threshold = data.get("confidence_threshold", 0.45)
                    self.debounce_seconds = data.get("debounce_seconds", 5)
            self._update_zone()
        except Exception as e:
            print(f"[Detector] Erro ao carregar config ROI: {e}")

    def save_roi_config(self, polygon: List[List[float]], confidence: Optional[float] = None, debounce: Optional[int] = None):
        data = {
            "polygon": polygon,
            "confidence_threshold": confidence if confidence is not None else self.confidence_threshold,
            "debounce_seconds": debounce if debounce is not None else self.debounce_seconds
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.polygon_normalized = polygon
        if confidence is not None:
            self.confidence_threshold = confidence
        if debounce is not None:
            self.debounce_seconds = debounce
        self._update_zone()

    def _update_zone(self):
        if self.current_frame_shape is None:
            return
        h, w = self.current_frame_shape[:2]
        pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in self.polygon_normalized], dtype=np.int32)
        self.zone = sv.PolygonZone(polygon=pts)
        self.zone_annotator = sv.PolygonZoneAnnotator(
            zone=self.zone,
            color=sv.Color.from_hex("#10B981"),
            thickness=3
        )

    def start(self):
        if self.running:
            return
        print("[Detector] Inicializando modelo OpenVINO...")
        self.model = YOLO(MODEL_PATH, task="detect")
        self.reader.start()
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        print("[Detector] Worker de detecção iniciado com sucesso!")

    def _run_loop(self):
        fps_monitor = sv.FPSMonitor()
        last_process_time = time.time()
        
        while self.running:
            # Cadência econômica: 2 FPS (processa 1 frame a cada ~500ms)
            time_to_wait = 0.5 - (time.time() - last_process_time)
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            last_process_time = time.time()

            raw_frame = self.reader.get_frame()
            if raw_frame is None:
                self.status["camera_online"] = False
                continue

            self.status["camera_online"] = True
            
            # Redimensiona para resolução ideal de inferência (640px de largura)
            orig_h, orig_w = raw_frame.shape[:2]
            scale = 640.0 / orig_w
            infer_w = 640
            infer_h = int(orig_h * scale)
            frame = cv2.resize(raw_frame, (infer_w, infer_h))

            if self.current_frame_shape != frame.shape:
                self.current_frame_shape = frame.shape
                self._update_zone()

            fps_monitor.tick()
            self.status["fps"] = round(fps_monitor.fps, 1)

            t0 = time.time()
            # Inferência filtrando estritamente class 15 ('cat')
            results = self.model.predict(
                frame,
                classes=[15],
                conf=self.confidence_threshold,
                device="cpu",
                verbose=False
            )[0]
            self.status["inference_ms"] = round((time.time() - t0) * 1000, 1)

            detections = sv.Detections.from_ultralytics(results)
            detections = self.tracker.update_with_detections(detections)

            cat_detected = len(detections) > 0
            self.status["cat_detected"] = cat_detected

            cat_in_zone = False
            if self.zone is not None and cat_detected:
                is_inside = self.zone.trigger(detections=detections)
                cat_in_zone = any(is_inside)

            self.status["cat_in_litterbox"] = cat_in_zone

            # Gestão do Evento de Visita
            now = datetime.now()
            now_ts = time.time()

            if cat_in_zone:
                self.last_seen_inside_time = now_ts
                if not self.is_visiting:
                    self.is_visiting = True
                    self.visit_start_time = now
                    self.current_video_filename = f"visita_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
                    video_filepath = os.path.join(RECORDINGS_DIR, self.current_video_filename)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    self.current_video_writer = cv2.VideoWriter(video_filepath, fourcc, 2.0, (infer_w, infer_h))
                    print(f"[Detector] Nova visita iniciada em {now.strftime('%H:%M:%S')} - Gravando clipe...")

            if self.is_visiting:
                duration = int((now - self.visit_start_time).total_seconds())
                self.status["is_visiting"] = True
                self.status["visit_duration"] = duration

                # Grava o frame no clipe
                if self.current_video_writer is not None:
                    self.current_video_writer.write(frame)

                # Verifica o debounce de saída
                if not cat_in_zone and (now_ts - self.last_seen_inside_time > self.debounce_seconds):
                    self.is_visiting = False
                    self.status["is_visiting"] = False
                    self.status["last_event_time"] = now.strftime("%H:%M:%S")
                    
                    if self.current_video_writer is not None:
                        self.current_video_writer.release()
                        self.current_video_writer = None

                    # Apenas salva visitas reais com pelo menos 3 segundos de permanência
                    if duration >= 3:
                        record_visit(
                            start_time=self.visit_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time=now.strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=duration,
                            video_filename=self.current_video_filename
                        )
                        print(f"[Detector] Visita concluída! Duração: {duration}s. Registro salvo no banco.")
                    else:
                        # Descarta falsos disparos relâmpago
                        try:
                            os.remove(os.path.join(RECORDINGS_DIR, self.current_video_filename))
                        except Exception:
                            pass
                        print(f"[Detector] Visita curta demais ({duration}s), clipe descartado.")

            # Anotações visuais no frame para o feed
            annotated_frame = frame.copy()
            if self.zone_annotator and self.zone:
                self.zone_annotator.color = sv.Color.from_hex("#EF4444") if cat_in_zone else sv.Color.from_hex("#10B981")
                annotated_frame = self.zone_annotator.annotate(scene=annotated_frame)
            if len(detections) > 0:
                annotated_frame = self.box_annotator.annotate(scene=annotated_frame, detections=detections)
                labels = [f"Gata #{tid} ({conf:.0%})" for tid, conf in zip(detections.tracker_id, detections.confidence)]
                annotated_frame = self.label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)
                annotated_frame = self.trace_annotator.annotate(scene=annotated_frame, detections=detections)

            # Codifica em JPEG para o feed web
            ret_jpg, jpeg_buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ret_jpg:
                with self.lock:
                    self.latest_annotated_jpeg = jpeg_buf.tobytes()

    def get_annotated_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_annotated_jpeg

    def stop(self):
        self.running = False
        if self.current_video_writer is not None:
            self.current_video_writer.release()
        self.reader.stop()


# Instância global singleton do Detector
detector = CatCamDetector()

if __name__ == "__main__":
    detector.start()
    print("Detector rodando no terminal para teste... Pressione Ctrl+C para sair.")
    try:
        while True:
            time.sleep(2)
            print(f"[Status] Câmera: {detector.status['camera_online']} | Gato detectado: {detector.status['cat_detected']} | Na caixa: {detector.status['cat_in_litterbox']} | FPS: {detector.status['fps']} | Latência: {detector.status['inference_ms']}ms")
    except KeyboardInterrupt:
        detector.stop()
        print("Detector finalizado.")
