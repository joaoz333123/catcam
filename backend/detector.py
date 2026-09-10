import os
import sys
import json
import time
import threading
import collections
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

MODE_CLASSES = {
    "cat": [15],
    "dog": [16],
    "person": [0],
    "vehicles": [2, 3, 5, 7],
    "all": None
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
    if color_filter == "none" or crop_bgr is None or crop_bgr.size == 0:
        return True
    try:
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        total_pixels = crop_bgr.shape[0] * crop_bgr.shape[1]
        if total_pixels == 0:
            return True

        if color_filter == "white":
            mask = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 55, 255]))
            return (np.sum(mask > 0) / total_pixels) > 0.25

        elif color_filter == "black":
            mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 65]))
            return (np.sum(mask > 0) / total_pixels) > 0.25

        elif color_filter == "red":
            mask1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
            mask2 = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
            mask = mask1 | mask2
            return (np.sum(mask > 0) / total_pixels) > 0.20
    except Exception:
        pass
    return True


class FreshFrameReader(threading.Thread):
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
                time.sleep(1.5)
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
        
        # Buffer de Suavização (Jitter Buffer) para eliminação de travadas
        # Armazena até 45 frames (~2 a 3 segundos de buffer contínuo)
        self.frame_buffer = collections.deque(maxlen=60)
        
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
            "inference_ms": 0.0,
            "buffer_depth": 0
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
        print(f"[Detector] Worker iniciado a {self.target_fps} FPS no modo '{self.target_mode}' com Buffer de Suavizacao ativo.")

    def _run_loop(self):
        fps_monitor = sv.FPSMonitor()
        last_process_time = time.perf_counter()
        
        while self.running:
            target_delay = 1.0 / max(1, self.target_fps)
            elapsed = time.perf_counter() - last_process_time
            time_to_wait = target_delay - elapsed
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            last_process_time = time.perf_counter()

            raw_frame = self.reader.get_frame()
            if raw_frame is None:
                self.status["camera_online"] = False
                continue

            self.status["camera_online"] = True
            
            orig_h, orig_w = raw_frame.shape[:2]
            scale = 640.0 / orig_w
            infer_w = 640
            infer_h = int(orig_h * scale)
            frame = cv2.resize(raw_frame, (infer_w, infer_h), interpolation=cv2.INTER_LINEAR)

            if self.current_frame_shape != frame.shape:
                self.current_frame_shape = frame.shape
                self._update_zone()

            fps_monitor.tick()
            self.status["fps"] = round(fps_monitor.fps, 1)

            target_classes = MODE_CLASSES.get(self.target_mode, [15])

            t0 = time.perf_counter()
            results = self.model.predict(
                frame,
                classes=target_classes,
                conf=self.confidence_threshold,
                device="cpu",
                verbose=False
            )[0]
            self.status["inference_ms"] = round((time.perf_counter() - t0) * 1000, 1)

            detections = sv.Detections.from_ultralytics(results)

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
            self.status["cat_in_litterbox"] = obj_in_zone

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
                    self.current_video_writer = cv2.VideoWriter(video_filepath, fourcc, float(self.target_fps), (infer_w, infer_h))
                    print(f"[Detector] Evento iniciado em {now.strftime('%H:%M:%S')} - Gravando clipe fluido...")

            if self.is_visiting:
                duration = int((now - self.visit_start_time).total_seconds())
                self.status["is_visiting"] = True
                self.status["visit_duration"] = duration

                if self.current_video_writer is not None:
                    self.current_video_writer.write(frame)

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

            # Anotações visuais da IA
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

            # Codifica com otimização rápida
            ret_jpg, jpeg_buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret_jpg:
                jpeg_bytes = jpeg_buf.tobytes()
                with self.lock:
                    self.latest_annotated_jpeg = jpeg_bytes
                    self.frame_buffer.append(jpeg_bytes)
                    self.status["buffer_depth"] = len(self.frame_buffer)

    def generate_smooth_stream(self):
        """
        Gerador de streaming com Jitter Buffer (Metrônomo de Precisão):
        Acumula uma pequena reserva inicial (~1 segundo) e reproduz
        com cadência perfeitamente uniforme, eliminando 100% dos microsoluços.
        """
        preroll_target = max(6, int(self.target_fps * 1.0))
        
        # Aguarda encher o pre-roll inicial
        while self.running and len(self.frame_buffer) < preroll_target:
            time.sleep(0.04)

        interval = 1.0 / max(1, self.target_fps)
        last_tick = time.perf_counter()

        while self.running:
            frame_data = None
            with self.lock:
                buf_len = len(self.frame_buffer)
                if buf_len > 0:
                    # Se o buffer acumular mais de 2.5 segundos, descarta os mais antigos para não estourar atraso
                    if buf_len > int(self.target_fps * 2.5):
                        self.frame_buffer.popleft()
                    frame_data = self.frame_buffer.popleft()
                elif self.latest_annotated_jpeg is not None:
                    frame_data = self.latest_annotated_jpeg

            if frame_data is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")

            # Ritmo preciso de cinema (metrônomo)
            now = time.perf_counter()
            sleep_time = interval - (now - last_tick)
            if sleep_time > 0:
                time.sleep(sleep_time)
            last_tick = time.perf_counter()

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
            print(f"[Status] Câmera: {detector.status['camera_online']} | FPS: {detector.status['fps']} | Buffer: {detector.status['buffer_depth']} frames")
    except KeyboardInterrupt:
        detector.stop()
