import os
import sys
import json
import time
import threading
import subprocess
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

try:
    from winotify import Notification, audio
    WINOTIFY_AVAILABLE = True
except ImportError:
    WINOTIFY_AVAILABLE = False

def send_windows_notification_async(title: str, msg: str):
    if not WINOTIFY_AVAILABLE:
        return
    def _worker():
        try:
            toast = Notification(
                app_id="CatCam AI Vision",
                title=title,
                msg=msg,
                duration="short"
            )
            toast.set_audio(audio.Default, loop=False)
            toast.add_actions(label="Ver ao Vivo", launch="http://localhost:8000")
            toast.show()
        except Exception as e:
            print(f"[Notifier] Erro ao disparar toast do Windows: {e}")
    threading.Thread(target=_worker, daemon=True).start()

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "roi_config.json"))
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "yolo11n_openvino_model"))
RECORDINGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "recordings"))
RTSP_URL = "rtsp://localhost:8554/cat_cam"

os.makedirs(RECORDINGS_DIR, exist_ok=True)

MODE_CLASSES = {
    "cat": [15],
    "cat_beatriz": [15],
    "cat_serena": [15],
    "dog": [16],
    "person": [0],
    "vehicles": [2, 3, 5, 7],
    "all": None
}

CLASS_NAMES_PT = {
    0: "Pessoa", 1: "Bicicleta", 2: "Carro", 3: "Moto", 4: "Avião", 5: "Ônibus", 6: "Trem", 7: "Caminhão", 8: "Barco",
    9: "Semáforo", 10: "Hidrante", 11: "Placa de Pare", 12: "Parquímetro", 13: "Banco", 14: "Pássaro", 15: "Gato",
    16: "Cachorro", 17: "Cavalo", 18: "Ovelha", 19: "Vaca", 20: "Elefante", 21: "Urso", 22: "Zebra", 23: "Girafa",
    24: "Mochila", 25: "Guarda-chuva", 26: "Bolsa", 27: "Gravata", 28: "Mala", 29: "Frisbee", 30: "Esqui",
    31: "Snowboard", 32: "Bola de Esportes", 33: "Pipa", 34: "Taco de Beisebol", 35: "Luva de Beisebol",
    36: "Skate", 37: "Prancha de Surfe", 38: "Raquete de Tênis", 39: "Garrafa", 40: "Taça de Vinho", 41: "Copo",
    42: "Garfo", 43: "Faca", 44: "Colher", 45: "Tigela", 46: "Banana", 47: "Maçã", 48: "Sanduíche", 49: "Laranja",
    50: "Brócolis", 51: "Cenoura", 52: "Cachorro-quente", 53: "Pizza", 54: "Donut", 55: "Bolo", 56: "Cadeira",
    57: "Sofá", 58: "Planta em Vaso", 59: "Cama", 60: "Mesa de Jantar", 61: "Vaso Sanitário", 62: "TV / Monitor",
    63: "Notebook", 64: "Mouse", 65: "Controle Remoto", 66: "Teclado", 67: "Celular", 68: "Micro-ondas",
    69: "Forno", 70: "Torradeira", 71: "Pia", 72: "Geladeira", 73: "Livro", 74: "Relógio", 75: "Vaso",
    76: "Tesoura", 77: "Urso de Pelúcia", 78: "Secador de Cabelo", 79: "Escova de Dentes"
}

def identify_cat_individual(crop_bgr: np.ndarray, full_frame_bgr: Optional[np.ndarray] = None) -> str:
    """
    Identifica se o gato recortado é a Beatriz (Amarela/Laranja) ou a Serena (Cinza).
    Calibrado especificamente com as assinaturas cromáticas das fotos reais da Serena:
    - Serena: Pelagem cinza-ardósia / azul britânico / lilac, caracterizada por tonalidade fria (B >= R - 5),
      matiz HSV entre 70 e 135 (azul/ardósia) e baixa/média saturação (S <= 100), além de cinza neutro (S <= 40).
    - Beatriz: Pelagem quente amarela/laranja com forte dominância vermelha (R > B + 20) e matiz quente (Hue 8 a 36).
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return "Gato"

    # 1. Verifica se a imagem geral da câmera está em infravermelho (monocromática / visão noturna)
    if full_frame_bgr is not None and full_frame_bgr.size > 0:
        b_f, g_f, r_f = cv2.split(full_frame_bgr)
        diff_rg = float(np.mean(cv2.absdiff(r_f, g_f)))
        diff_gb = float(np.mean(cv2.absdiff(g_f, b_f)))
        if diff_rg < 4.0 and diff_gb < 4.0:
            return "Gato (Noturno)"

    try:
        h, w = crop_bgr.shape[:2]
        # Ponderação central (core crop) de 10% para evitar interferência do fundo
        # (ex: armário de madeira marrom/dourado ao lado ou piso)
        y1, y2 = int(h * 0.10), int(h * 0.90)
        x1, x2 = int(w * 0.10), int(w * 0.90)
        core = crop_bgr[y1:y2, x1:x2] if (y2 > y1 and x2 > x1) else crop_bgr

        hsv = cv2.cvtColor(core, cv2.COLOR_BGR2HSV)
        b, g, r = cv2.split(core)
        total_pixels = core.shape[0] * core.shape[1]
        if total_pixels == 0:
            return "Gato"

        # Beatriz: Amarelo / Laranja / Ruivo (Calibrado com foto real: Hue 8-34, Sat >= 50, Val >= 48, R > B + 26)
        yellow_hue = (hsv[:,:,0] >= 8) & (hsv[:,:,0] <= 34)
        yellow_sat_val = (hsv[:,:,1] >= 50) & (hsv[:,:,2] >= 48)
        red_dominance = (r.astype(int) - b.astype(int)) > 26
        beatriz_mask = yellow_hue & yellow_sat_val & red_dominance
        beatriz_score = float(np.sum(beatriz_mask)) / total_pixels

        # Serena: Cinza / Azul Ardósia das imagens reais
        # A) Cinza neutro tradicional (baixa saturação Sat <= 40, Val 35-220)
        gray_neutral = (hsv[:,:,1] <= 40) & (hsv[:,:,2] >= 35) & (hsv[:,:,2] <= 220)
        # B) Cinza-azulado / Ardósia característico da pelagem da Serena sob a câmera
        # (canal azul frio B >= R - 5, Hue 70-135, Sat 15-100, Val 35-225)
        slate_hue = (hsv[:,:,0] >= 70) & (hsv[:,:,0] <= 135)
        slate_sat_val = (hsv[:,:,1] >= 15) & (hsv[:,:,1] <= 100) & (hsv[:,:,2] >= 35) & (hsv[:,:,2] <= 225)
        cool_dominance = (b.astype(int) >= (r.astype(int) - 5))
        gray_slate = slate_hue & slate_sat_val & cool_dominance

        serena_mask = gray_neutral | gray_slate
        serena_score = float(np.sum(serena_mask)) / total_pixels

        # Classificação robusta calibrada para ambas as gatas reais
        if beatriz_score > 0.20 and beatriz_score > (serena_score * 1.25):
            return "Beatriz (Amarela)"
        elif serena_score > beatriz_score:
            return "Serena (Cinza)"
        else:
            return "Beatriz (Amarela)" if beatriz_score >= 0.18 else "Serena (Cinza)"
    except Exception:
        return "Gato"

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


def convert_video_to_h264(filepath: str):
    """
    Converte o arquivo de vídeo gerado para H.264 (avc1) com moov atom no início (+faststart).
    Isso é 100% obrigatório para reprodução nativa em navegadores HTML5 (Chrome, Edge, Safari).
    """
    def _worker():
        if not os.path.exists(filepath):
            return
        tmp_path = filepath + ".tmp.mp4"
        try:
            cmd = [
                "ffmpeg", "-y", "-i", filepath,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                tmp_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                os.replace(tmp_path, filepath)
                print(f"[Detector] Vídeo convertido para H.264 Web compatível: {os.path.basename(filepath)}")
            elif os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception as e:
            print(f"[Detector] Erro ao converter vídeo para H.264: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    threading.Thread(target=_worker, daemon=True).start()


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
        self.visit_cat_counts = {"Beatriz": 0, "Serena": 0, "Noturno": 0}
        self.visit_other_counts: Dict[str, int] = collections.defaultdict(int)
        
        self.target_cats: List[str] = ["beatriz", "serena"]
        self.target_presets: List[str] = ["cats"]
        self.extra_classes: List[int] = []
        self.notifications_enabled: bool = True
        self.last_notification_time: float = 0.0
        self.last_notified_target: str = ""

        # Telemetria ao vivo
        self.status: Dict[str, Any] = {
            "camera_online": False,
            "target_mode": "cat",
            "color_filter": "none",
            "target_fps": 15,
            "target_cats": self.target_cats,
            "target_presets": self.target_presets,
            "extra_classes": self.extra_classes,
            "notifications_enabled": self.notifications_enabled,
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
        self.latest_ai_payload: Dict[str, Any] = {
            "objects": [],
            "in_zone": False,
            "in_zone_count": 0,
            "polygon": self.polygon_normalized,
            "fps": 0.0,
            "inference_ms": 0.0,
            "alert": None,
            "ts": 0.0
        }
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
                    self.target_cats = data.get("target_cats", ["beatriz", "serena"])
                    self.target_presets = data.get("target_presets", ["cats"])
                    self.extra_classes = data.get("extra_classes", [])
                    self.notifications_enabled = data.get("notifications_enabled", True)

                    self.status["target_mode"] = self.target_mode
                    self.status["color_filter"] = self.color_filter
                    self.status["target_fps"] = self.target_fps
                    self.status["target_cats"] = self.target_cats
                    self.status["target_presets"] = self.target_presets
                    self.status["extra_classes"] = self.extra_classes
                    self.status["notifications_enabled"] = self.notifications_enabled
            self._update_zone()
        except Exception as e:
            print(f"[Detector] Erro ao carregar config ROI: {e}")

    def save_roi_config(self, polygon: Optional[List[List[float]]] = None, 
                        confidence: Optional[float] = None, 
                        debounce: Optional[int] = None,
                        target_fps: Optional[int] = None,
                        target_mode: Optional[str] = None,
                        color_filter: Optional[str] = None,
                        target_cats: Optional[List[str]] = None,
                        target_presets: Optional[List[str]] = None,
                        extra_classes: Optional[List[int]] = None,
                        notifications_enabled: Optional[bool] = None):
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
        if target_cats is not None:
            self.target_cats = target_cats
            self.status["target_cats"] = self.target_cats
        if target_presets is not None:
            self.target_presets = target_presets
            self.status["target_presets"] = self.target_presets
        if extra_classes is not None:
            self.extra_classes = extra_classes
            self.status["extra_classes"] = self.extra_classes
        if notifications_enabled is not None:
            self.notifications_enabled = notifications_enabled
            self.status["notifications_enabled"] = self.notifications_enabled

        data = {
            "polygon": self.polygon_normalized,
            "confidence_threshold": self.confidence_threshold,
            "debounce_seconds": self.debounce_seconds,
            "target_fps": self.target_fps,
            "target_mode": self.target_mode,
            "color_filter": self.color_filter,
            "target_cats": self.target_cats,
            "target_presets": self.target_presets,
            "extra_classes": self.extra_classes,
            "notifications_enabled": self.notifications_enabled
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

            # Combina classes ativas dos checkboxes + classes extras do multi-select
            active_classes = set()
            if "cats" in self.target_presets or len(self.target_cats) > 0:
                active_classes.add(15)
            if "dogs" in self.target_presets:
                active_classes.add(16)
            if "persons" in self.target_presets:
                active_classes.add(0)
            if "vehicles" in self.target_presets:
                active_classes.update([2, 3, 5, 7])
            if self.extra_classes:
                active_classes.update(self.extra_classes)
            if not active_classes:
                target_classes = MODE_CLASSES.get(self.target_mode, [15])
            else:
                target_classes = list(active_classes)

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
                    self.visit_cat_counts = {"Beatriz": 0, "Serena": 0, "Noturno": 0}
                    self.visit_other_counts = collections.defaultdict(int)
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

                    b_count = self.visit_cat_counts.get("Beatriz", 0)
                    s_count = self.visit_cat_counts.get("Serena", 0)
                    n_count = self.visit_cat_counts.get("Noturno", 0)

                    if b_count >= 5 and s_count >= 5 and (min(b_count, s_count) / max(1, max(b_count, s_count)) > 0.25):
                        visitor_name = "Ambos (Beatriz & Serena)"
                    elif b_count > s_count and b_count >= 2:
                        visitor_name = "Beatriz (Amarela)"
                    elif s_count > b_count and s_count >= 2:
                        visitor_name = "Serena (Cinza)"
                    elif n_count > 0 and (b_count == 0 and s_count == 0):
                        visitor_name = "Gato (Visão Noturna)"
                    elif self.visit_other_counts:
                        visitor_name = max(self.visit_other_counts.items(), key=lambda x: x[1])[0]
                    elif self.target_mode == "vehicles":
                        visitor_name = "Veículo"
                    elif self.target_mode == "person":
                        visitor_name = "Pessoa"
                    else:
                        visitor_name = "Gato"

                    if duration >= 3:
                        record_visit(
                            start_time=self.visit_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time=now.strftime("%Y-%m-%d %H:%M:%S"),
                            duration_seconds=duration,
                            video_filename=self.current_video_filename,
                            visitor_name=visitor_name
                        )
                        full_video_path = os.path.join(RECORDINGS_DIR, self.current_video_filename)
                        convert_video_to_h264(full_video_path)
                        print(f"[Detector] Evento concluído ({duration}s - {visitor_name}). Salvo e disparada conversão H.264 Web.")
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

            # Extrai payload de detecção estruturado para o Overlay WebRTC em tempo real
            objects_payload = []
            current_frame_cats = []
            if obj_count > 0:
                is_inside_list = self.zone.trigger(detections=detections) if self.zone is not None else [False] * obj_count
                for idx, (box, class_id, conf) in enumerate(zip(detections.xyxy, detections.class_id, detections.confidence)):
                    tracker_id = int(detections.tracker_id[idx]) if (detections.tracker_id is not None and detections.tracker_id[idx] is not None) else None
                    x1_n = round(float(box[0]) / infer_w, 4)
                    y1_n = round(float(box[1]) / infer_h, 4)
                    x2_n = round(float(box[2]) / infer_w, 4)
                    y2_n = round(float(box[3]) / infer_h, 4)
                    c_id = int(class_id)
                    inside = bool(is_inside_list[idx]) if idx < len(is_inside_list) else False

                    # Se for gato (15), identifica individualmente Beatriz (amarela) ou Serena (cinza)
                    if c_id == 15:
                        x1_p, y1_p = max(0, int(box[0])), max(0, int(box[1]))
                        x2_p, y2_p = min(infer_w, int(box[2])), min(infer_h, int(box[3]))
                        cat_crop = frame[y1_p:y2_p, x1_p:x2_p]
                        cat_identity = identify_cat_individual(cat_crop, raw_frame)
                        current_frame_cats.append(cat_identity)

                        if self.target_cats:
                            has_b = "beatriz" in self.target_cats
                            has_s = "serena" in self.target_cats
                            has_o = "other" in self.target_cats
                            if "Beatriz" in cat_identity and not has_b:
                                continue
                            if "Serena" in cat_identity and not has_s:
                                continue
                            if ("Noturno" in cat_identity or cat_identity == "Gato") and not (has_o or (has_b and has_s)):
                                continue

                        if self.target_mode == "cat_beatriz" and "Beatriz" not in cat_identity:
                            continue
                        if self.target_mode == "cat_serena" and "Serena" not in cat_identity:
                            continue

                        name = cat_identity
                    else:
                        name = CLASS_NAMES_PT.get(c_id, f"ID:{c_id}")

                    objects_payload.append({
                        "id": tracker_id if tracker_id is not None else int(idx),
                        "box": [x1_n, y1_n, x2_n, y2_n],
                        "class_id": c_id,
                        "label": f"{name} #{tracker_id}" if tracker_id is not None else name,
                        "name": name,
                        "conf": round(float(conf), 2),
                        "in_zone": inside
                    })

            if self.is_visiting and obj_in_zone:
                for c_name in current_frame_cats:
                    if "Beatriz" in c_name:
                        self.visit_cat_counts["Beatriz"] += 1
                    elif "Serena" in c_name:
                        self.visit_cat_counts["Serena"] += 1
                    elif "Noturno" in c_name:
                        self.visit_cat_counts["Noturno"] += 1
                for obj in objects_payload:
                    if obj.get("in_zone") and obj.get("class_id") != 15:
                        self.visit_other_counts[obj.get("name", "Objeto")] += 1

            # Disparo Imediato de Notificação Windows e Som (com cooldown anti-spam)
            alert_payload = None
            if obj_in_zone and self.notifications_enabled:
                current_alert_target = None
                for obj in objects_payload:
                    if obj.get("in_zone"):
                        current_alert_target = obj.get("name") or obj.get("label")
                        break

                if current_alert_target:
                    time_since_last = now_ts - self.last_notification_time
                    target_changed = (current_alert_target != self.last_notified_target)
                    if time_since_last > 25.0 or (target_changed and time_since_last > 6.0):
                        self.last_notification_time = now_ts
                        self.last_notified_target = current_alert_target
                        alert_payload = {
                            "target": current_alert_target,
                            "ts": now_ts
                        }
                        send_windows_notification_async(
                            title="🚨 Alerta CatCam AI",
                            msg=f"{current_alert_target} detectado(a) na área de interesse!"
                        )

            # Codifica com otimização rápida
            ret_jpg, jpeg_buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret_jpg:
                jpeg_bytes = jpeg_buf.tobytes()
                with self.lock:
                    self.latest_annotated_jpeg = jpeg_bytes
                    self.frame_buffer.append(jpeg_bytes)
                    self.status["buffer_depth"] = len(self.frame_buffer)
                    self.latest_ai_payload = {
                        "objects": objects_payload,
                        "in_zone": obj_in_zone,
                        "in_zone_count": in_zone_count,
                        "polygon": self.polygon_normalized,
                        "fps": self.status["fps"],
                        "inference_ms": self.status["inference_ms"],
                        "target_mode": self.target_mode,
                        "alert": alert_payload,
                        "ts": time.time()
                    }

    def get_latest_ai_payload(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.latest_ai_payload)

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
