import os
import json
import secrets
import hashlib
import hmac
from typing import Optional
from fastapi import Request, HTTPException, status, WebSocket

AUTH_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "auth.json"))

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

class AuthManager:
    def __init__(self):
        self.auth_enabled: bool = True
        self.salt: str = secrets.token_hex(16)
        self.password_hash: str = ""
        self.secret_key: str = secrets.token_hex(32)
        self.active_sessions: set = set()
        self.load_or_init_auth()

    def load_or_init_auth(self):
        if os.path.exists(AUTH_CONFIG_PATH):
            try:
                with open(AUTH_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.auth_enabled = data.get("auth_enabled", True)
                    self.salt = data.get("salt", self.salt)
                    self.password_hash = data.get("password_hash", "")
                    self.secret_key = data.get("secret_key", self.secret_key)
            except Exception as e:
                print(f"[Auth] Erro ao ler auth.json: {e}")
        else:
            # Senha padrão inicial: 'catcam2026' (pode ser alterada pelo painel ou no arquivo)
            initial_pw = "catcam2026"
            self.salt = secrets.token_hex(16)
            self.password_hash = _hash_password(initial_pw, self.salt)
            self.secret_key = secrets.token_hex(32)
            self.save_auth()
            print(f"[Auth] Configuração inicial de autenticação criada com senha padrão: '{initial_pw}'")

    def save_auth(self):
        os.makedirs(os.path.dirname(AUTH_CONFIG_PATH), exist_ok=True)
        data = {
            "auth_enabled": self.auth_enabled,
            "salt": self.salt,
            "password_hash": self.password_hash,
            "secret_key": self.secret_key
        }
        with open(AUTH_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def verify_password(self, password: str) -> bool:
        if not password:
            return False
        computed = _hash_password(password, self.salt)
        return hmac.compare_digest(computed, self.password_hash)

    def set_new_password(self, new_password: str) -> bool:
        if not new_password or len(new_password.strip()) < 3:
            return False
        self.salt = secrets.token_hex(16)
        self.password_hash = _hash_password(new_password.strip(), self.salt)
        self.active_sessions.clear()  # Invalida sessões antigas
        self.save_auth()
        return True

    def create_session_token(self) -> str:
        token = secrets.token_urlsafe(32)
        self.active_sessions.add(token)
        return token

    def is_session_valid(self, token: Optional[str]) -> bool:
        if not self.auth_enabled:
            return True
        if not token:
            return False
        return token in self.active_sessions

    def revoke_session(self, token: Optional[str]):
        if token and token in self.active_sessions:
            self.active_sessions.remove(token)

auth_manager = AuthManager()

def require_auth(request: Request):
    """
    Dependência para rotas FastAPI protegidas.
    Verifica se o cookie de sessão ou cabeçalho 'X-Session-Token' é válido.
    """
    if not auth_manager.auth_enabled:
        return True

    token = request.cookies.get("catcam_session") or request.headers.get("X-Session-Token")
    if not auth_manager.is_session_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado. Por favor, faça login."
        )
    return True

def verify_ws_auth(websocket: WebSocket) -> bool:
    """
    Verifica a autenticação para conexões WebSocket.
    Lê o cookie 'catcam_session' ou o parâmetro de query '?token=...'.
    """
    if not auth_manager.auth_enabled:
        return True

    token = websocket.cookies.get("catcam_session")
    if not token:
        query_str = websocket.scope.get("query_string", b"").decode("utf-8")
        from urllib.parse import parse_qs
        params = parse_qs(query_str)
        token = params.get("token", [None])[0]

    return auth_manager.is_session_valid(token)
