"""
CatCam AI Monitor - Aplicativo de Bandeja do Sistema (System Tray)
Gerencia a inicialização e encerramento em segundo plano dos serviços do CatCam
com menu de clique direito, atalhos para a live e atalho nativo no Desktop.
"""

import os
import sys
import time
import json
import threading
import subprocess
import webbrowser
import ctypes
from typing import Optional
from PIL import Image
import pystray

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
ICON_PATH = os.path.join(ASSETS_DIR, "catcam.png")
CONFIG_FILE = os.path.join(CONFIG_DIR, "roi_config.json")
RECORDINGS_DIR = os.path.join(PROJECT_DIR, "data", "recordings")

VENV_PYTHON = os.path.join(PROJECT_DIR, ".venv", "Scripts", "python.exe")
GO2RTC_EXE = os.path.join(PROJECT_DIR, "bin", "go2rtc.exe")

CREATE_NO_WINDOW = 0x08000000

class CatCamTrayApp:
    def __init__(self, mutex=None):
        self.mutex = mutex
        self.go2rtc_proc: Optional[subprocess.Popen] = None
        self.uvicorn_proc: Optional[subprocess.Popen] = None
        self.tunnel_proc: Optional[subprocess.Popen] = None
        self.public_url: str = ""
        self.running: bool = True
        self.icon: Optional[pystray.Icon] = None

        self.load_public_url_from_config()

    def load_public_url_from_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.public_url = data.get("public_url", "")
            except Exception:
                pass

    def save_public_url_to_config(self, url: str):
        self.public_url = url
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["public_url"] = url
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    def is_port_in_use(self, port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def start_services(self):
        # 1. Iniciar go2rtc se não estiver rodando
        if not self.is_port_in_use(1984):
            go2rtc_yaml = os.path.join(CONFIG_DIR, "go2rtc.yaml")
            if os.path.exists(GO2RTC_EXE) and os.path.exists(go2rtc_yaml):
                self.go2rtc_proc = subprocess.Popen(
                    [GO2RTC_EXE, "-config", go2rtc_yaml],
                    cwd=PROJECT_DIR,
                    creationflags=CREATE_NO_WINDOW
                )
            time.sleep(1)

        # 2. Iniciar servidor FastAPI / IA se porta 8000 não estiver em uso
        if not self.is_port_in_use(8000):
            python_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            self.uvicorn_proc = subprocess.Popen(
                [python_bin, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=PROJECT_DIR,
                creationflags=CREATE_NO_WINDOW
            )
            time.sleep(2)

        # 3. Iniciar Túnel SSH em thread separada
        threading.Thread(target=self._run_ssh_tunnel, daemon=True).start()

    def _run_ssh_tunnel(self):
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-R", "80:localhost:8000",
            "nokey@localhost.run"
        ]
        try:
            self.tunnel_proc = subprocess.Popen(
                cmd,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=CREATE_NO_WINDOW
            )
            for line in self.tunnel_proc.stdout:
                if not self.running:
                    break
                if "tunneled with tls" in line or "lhr.life" in line:
                    for part in line.split():
                        if "http://" in part or "https://" in part:
                            clean = part.strip().rstrip(",.")
                            if "https://" in clean:
                                self.public_url = clean
                                self.save_public_url_to_config(clean)
                                self._update_tray_menu()
                                break
        except Exception:
            pass

    def stop_services(self):
        self.running = False
        
        # Encerra túnel
        if self.tunnel_proc:
            try:
                self.tunnel_proc.terminate()
            except Exception:
                pass

        # Encerra uvicorn
        if self.uvicorn_proc:
            try:
                self.uvicorn_proc.terminate()
            except Exception:
                pass

        # Encerra go2rtc
        if self.go2rtc_proc:
            try:
                self.go2rtc_proc.terminate()
            except Exception:
                pass

        # Limpeza forçada com taskkill para garantir zero processos fantasmas
        try:
            subprocess.run(["taskkill", "/F", "/IM", "go2rtc.exe"], creationflags=CREATE_NO_WINDOW, check=False)
            subprocess.run(
                'for /f "tokens=5" %a in (\'netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"\') do taskkill /F /PID %a',
                shell=True,
                creationflags=CREATE_NO_WINDOW,
                check=False
            )
        except Exception:
            pass

    def copy_to_clipboard(self, text: str):
        if not text:
            return
        try:
            proc = subprocess.Popen(['clip'], stdin=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            proc.communicate(input=text.encode('utf-8'))
        except Exception:
            pass

    def _open_local_web(self, icon, item):
        webbrowser.open("http://localhost:8000")

    def _open_remote_web(self, icon, item):
        url = self.public_url or "http://localhost:8000"
        webbrowser.open(url)

    def _copy_remote_link(self, icon, item):
        url = self.public_url or "http://localhost:8000"
        self.copy_to_clipboard(url)

    def _open_recordings_folder(self, icon, item):
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        os.startfile(RECORDINGS_DIR)

    def _on_exit(self, icon, item):
        self.stop_services()
        if self.mutex:
            try:
                ctypes.windll.kernel32.CloseHandle(self.mutex)
            except Exception:
                pass
            self.mutex = None
        if self.icon:
            self.icon.stop()

    def _build_menu(self):
        remote_label = f"📱 Abrir Link Online ({self.public_url})" if self.public_url else "📱 Abrir Link Online"
        return pystray.Menu(
            pystray.MenuItem("🐱 CatCam AI Monitor (🟢 Ativo)", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🌐 Abrir Painel (Local)", self._open_local_web, default=True),
            pystray.MenuItem(remote_label, self._open_remote_web),
            pystray.MenuItem("📋 Copiar Link de Acesso", self._copy_remote_link),
            pystray.MenuItem("📁 Abrir Pasta de Gravações", self._open_recordings_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Encerrar CatCam", self._on_exit)
        )

    def _update_tray_menu(self):
        if self.icon:
            self.icon.menu = self._build_menu()
            tooltip = f"CatCam AI - Online: {self.public_url}" if self.public_url else "CatCam AI Monitor"
            self.icon.title = tooltip[:120]

    def run(self):
        # Carrega ícone
        if os.path.exists(ICON_PATH):
            image = Image.open(ICON_PATH)
        else:
            image = Image.new('RGB', (64, 64), color=(99, 102, 241))

        # Inicia serviços em segundo plano
        self.start_services()

        # Abre o navegador local automaticamente no boot
        webbrowser.open("http://localhost:8000")

        # Inicia o ícone de bandeja
        self.icon = pystray.Icon(
            "CatCamAI",
            image,
            "CatCam AI Monitor (🟢 Ativo)",
            menu=self._build_menu()
        )
        self.icon.run()

def get_single_instance_mutex():
    ERROR_ALREADY_EXISTS = 183
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "CatCamAI_SingleInstance_Mutex")
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
        return None
    return mutex

if __name__ == "__main__":
    mutex = get_single_instance_mutex()
    if mutex is None:
        # A CatCam já está em execução em segundo plano na bandeja!
        # Apenas foca/abre o painel no navegador padrão e encerra este novo processo para evitar instâncias duplicadas
        webbrowser.open("http://localhost:8000")
        sys.exit(0)

    app = CatCamTrayApp(mutex=mutex)
    app.run()
