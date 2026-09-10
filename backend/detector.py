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

# Mapeamento de modos e classes do COCO Dataset
MODE_CLASSES = {
    "cat": [15],                     # Gato
    "dog": [16],                     # Cachorro
    "person": [0],                   # Pessoa
    "vehicles": [2, 3, 5, 7],        # Carro, Moto, Ônibus, Caminhão
    "all": None                      # Todas as classes
}

CLASS_NAMES_PT = {
    0: "Pessoa",
    1: "Bicicleta",
    2: "Carro",
    3: "Moto",
    5: "Ônibus",
    7: "Caminhão",
    15: "Gato",
    16: "Cachorro"
}

def is_matching_color(crop_bgr: np.ndarray, color_filter: str) -> bool:
    """Verifica se o recorte do objeto detectado corresponde ao filtro de cor desejado."""
    if color_filter == "none" or crop_bgr is None or crop_bgr.size == 0:
        return True
    
    try:
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        total_pixels = crop_bgr.shape[0] * crop_bgr.shape[1]
        if total_pixels == 0:
            return True

        if color_filter == "white":
            # Branco: Saturação baixa (< 55) e alto brilho (> 160)
            mask = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 55, 255]))
            return (np.sum(mask > 0) / total_pixels) > 0.25

        elif color_filter == "black":
            # Preto: Brilho muito baixo (< 65)
            mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 65]))
            return (np.sum(mask > 0) / total_pixels) > 0.25

        elif color_filter == "red":
            # Vermelho: dois intervalos no HSV (0-10 e 170-180)
            mask1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
            mask2 = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
            mask = mask1 | mask2
            return (np.sum(mask > 0) / total_pixels) > 0.20
    except Exception:
        pass
    return True


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
        self.target_fps = 15
        self.target_mode = "cat"
        self.color_filter = "none"
        self.current_frame_shape = None
        
        # Estado de visita/permanência
        self.is_visiting = False
        self.visit_start_time = None
        self.last_seen_inside_time = 0
        self.current_video_writer = None
        self.current_video_filename = None
        
        # Telemetria ao vivo
        self.status: Dict[str, Any] = {
            "camera_online": False,
            "target_mode": "cat",
            "color_filter": "none",
            "target_fps": 15,
            "detected_count": 0,
            "in_zone_count": 0,
            "object_detected": False,
            "object_in_zone": False,
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
                    self.target_fps = data.get("target_fps", 15)
                    self.target_mode = data.get("target_mode", "cat")
                    self.color_filter = data.get("color_filter", "none")
                    self.status["target_mode"] = self.target_mode
                    self.status["color_filter"] = self.color_filter
                    self.status["target_fps"] = self.target_fps
            self._update_zone()
        except Exception as e:
            print(f"[Detector] Erro ao carregar config ROI: {e}")

    def save_roi_config(self, polygon: Optional[List[List[float]]] = None, 
                        confidence: Optional[float] = None, 
                        debounce: Optional[int] = None,
                        target_fps: Optional[int] = None,
                        target_mode: Optional[str] = None,
                        color_filter: Optional[str] = None):
        if polygon is not None:
            self.polygon_normalized = polygon
        if confidence is not None:
            self.confidence_threshold = confidence
        if debounce is not None:
            self.debounce_seconds = debounce
        if target_fps is not None:
            self.target_fps = max(1, min(30, target_fps))
            self.status["target_fps"] = self.target_fps
        if target_mode is not None:
            self.target_mode = target_mode
            self.status["target_mode"] = self.target_mode
        if color_filter is not None:
            self.color_filter = color_filter
            self.status["color_filter"] = self.color_filter

        data = {
            "polygon": self.polygon_normalized,
            "confidence_threshold": self.confidence_threshold,
            "debounce_seconds": self.debounce_seconds,
            "target_fps": self.target_fps,
            "target_mode": self.target_mode,
            "color_filter": self.color_filter
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
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
        print(f"[Detector] Worker iniciado a {self.target_fps} FPS no modo '{self.target_mode}'!")

    def _run_loop(self):
        fps_monitor = sv.FPSMonitor()
        last_process_time = time.time()
        
        while self.running:
            # Cadência configurável (ex: 15 FPS -> ~66ms entre frames)
            target_delay = 1.0 / max(1, self.target_fps)
            time_to_wait = target_delay - (time.time() - last_process_time)
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            last_process_time = time.time()

            raw_frame = self.reader.get_frame()
            if raw_frame is None:
                self.status["camera_online"] = False
                continue

            self.status["camera_online"] = True
            
            # Redimensiona para resolução de inferência (640px)
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

            # Define as classes de interesse de acordo com o modo
            target_classes = MODE_CLASSES.get(self.target_mode, [15])

            t0 = time.time()
            results = self.model.predict(
                frame,
                classes=target_classes,
                conf=self.confidence_threshold,
                device="cpu",
                verbose=False
            )[0]
            self.status["inference_ms"] = round((time.time() - t0) * 1000, 1)

            detections = sv.Detections.from_ultralytics(results)

            # Filtro opcional de cor (ex: carros brancos)
            if self.color_filter != "none" and len(detections) > 0:
                keep_indices = []
                for idx, box in enumerate(detections.xyxy):
                    x1, y1, x2, y2 = map(int, box)
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(infer_w, x2), min(infer_h, y2)
                    crop = frame[y1:y2, x1:x2]
                    if is_matching_color(crop, self.color_filter):
                        keep_indices.append(idx)
                detections = detections[np.array(keep_indices, dtype=int)] if len(keep_indices) > 0 else sv.Detections.empty()

            detections = self.tracker.update_with_detections(detections)

            obj_count = len(detections)
            self.status["detected_count"] = obj_count
            self.status["object_detected"] = obj_count > 0

            in_zone_count = 0
            obj_in_zone = False
            if self.zone is not None and obj_count > 0:
                is_inside = self.zone.trigger(detections=detections)
                in_zone_count = int(np.sum(is_inside))
                obj_in_zone = in_zone_count > 0

            self.status["in_zone_count"] = in_zone_count
            self.status["object_in_zone"] = obj_in_zone
            self.status["cat_in_litterbox"] = obj_in_zone # compatibilidade

            # Gestão do Evento de Visita / Presença
            now = datetime.now()
            now_ts = time.time()

            if obj_in_zone:
                self.last_seen_inside_time = now_ts
                if not self.is_visiting:
                    self.is_visiting = True
                    self.visit_start_time = now
                    self.current_video_filename = f"evento_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
                    video_filepath = os.path.join(RECORDINGS_DIR, self.current_video_filename)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    # Grava no FPS alvo para fluidez natural
                    self.current_video_writer = cv2.VideoWriter(video_filepath, fourcc, float(self.target_fps), (infer_w, infer_h))
                    print(f"[Detector] Evento iniciado em {now.strftime('%H:%M:%S')} - Gravando...")

            if self.is_visiting:
                duration = int((now - self.visit_start_time).total_seconds())
                self.status["is_visiting"] = True
                self.status["visit_duration"] = duration

                # Grava frame
                if self.current_video_writer is not None:
                    self.current_video_writer.write(frame)

                # Debounce de saída
                if not obj_in_zone and (now_ts - self.last_seen_inside_time > self.debounce_seconds):
                    self.is_visiting = False
                    self.status["is_visiting"] = False
                    self.status["last_event_time"] = now.strftime("%H:%M:%S")
                    
                    if self.current_video_writer is not None:
                        self.current_video_writer.release()
                        self.current_video_writer = None

                    if duration >= 3:
                        record_visit(
                            start_time=self.visit_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time=now.strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=duration,
                            video_filename=self.current_video_filename
                        )
                        print(f"[Detector] Evento concluído ({duration}s). Salvo no banco de dados.")
                    else:
                        try:
                            os.remove(os.path.join(RECORDINGS_DIR, self.current_video_filename))
                        except Exception:
                            pass

            # Anotações Visuais
            annotated_frame = frame.copy()
            if self.zone_annotator and self.zone:
                self.zone_annotator.color = sv.Color.from_hex("#EF4444") if obj_in_zone else sv.Color.from_hex("#10B981")
                annotated_frame = self.zone_annotator.annotate(scene=annotated_frame)

            if obj_count > 0:
                annotated_frame = self.box_annotator.annotate(scene=annotated_frame, detections=detections)
                
                labels = []
                for class_id, tracker_id, conf in zip(detections.class_id, detections.tracker_id, detections.confidence):
                    name = CLASS_NAMES_PT.get(int(class_id), f"ID:{class_id}")
                    if tracker_id is not None:
                        labels.append(f"{name} #{tracker_id} ({conf:.0%})")
                    else:
                        labels.append(f"{name} ({conf:.0%})")

                annotated_frame = self.label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)
                annotated_frame = self.trace_annotator.annotate(scene=annotated_frame, detections=detections)

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


# Instância global
detector = CatCamDetector()

if __name__ == "__main__":
    detector.start()
    print("Detector iniciado. Pressione Ctrl+C para sair.")
    try:
        while True:
            time.sleep(2)
            print(f"[Status] Câmera: {detector.status['camera_online']} | FPS: {detector.status['fps']} | Objetos: {detector.status['detected_count']} | Na Zona: {detector.status['in_zone_count']}")
    except KeyboardInterrupt:
        detector.stop()
