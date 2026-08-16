"""Sesión del agente: login con las mismas credenciales de la web."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger("digitalizador-agent")

SESSION_NAME = "session.json"


class AgentSession:
    def __init__(self, base_url: str, session_path: Path) -> None:
        self.base = base_url.rstrip("/")
        self.path = session_path
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.expires_at: float | None = None
        self.email: str | None = None
        self.user_id: str | None = None
        self.nombre: str | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.expires_at = data.get("expires_at")
            self.email = data.get("email")
            self.user_id = data.get("user_id")
            self.nombre = data.get("nombre")
        except Exception as exc:
            log.warning("No se pudo leer sesión guardada: %s", exc)

    def _save(self) -> None:
        payload = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "email": self.email,
            "user_id": self.user_id,
            "nombre": self.nombre,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.email = None
        self.user_id = None
        self.nombre = None
        if self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass

    def has_tokens(self) -> bool:
        return bool(self.access_token and self.refresh_token)

    def _apply_login_response(self, data: dict[str, Any]) -> None:
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        expires_at = data.get("expires_at")
        if expires_at is None and data.get("expires_in"):
            expires_at = int(time.time()) + int(data["expires_in"])
        self.expires_at = float(expires_at) if expires_at is not None else None
        user = data.get("user") or {}
        self.user_id = user.get("id") or self.user_id
        self.email = user.get("email") or self.email
        if user.get("nombre"):
            self.nombre = user["nombre"]
        self._save()

    def login(self, email: str, password: str) -> None:
        r = requests.post(
            f"{self.base}/api/public/agente/login",
            json={"email": email.strip().lower(), "password": password},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if r.status_code != 200:
            detail = ""
            try:
                detail = (r.json() or {}).get("error") or r.text
            except Exception:
                detail = r.text
            raise RuntimeError(detail or f"Login falló ({r.status_code})")
        self._apply_login_response(r.json())
        log.info("Sesión iniciada como %s", self.email or email)

    def refresh(self) -> bool:
        if not self.refresh_token:
            return False
        r = requests.post(
            f"{self.base}/api/public/agente/refresh",
            json={"refresh_token": self.refresh_token},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if r.status_code != 200:
            return False
        self._apply_login_response(r.json())
        return True

    def ensure_access_token(self) -> str:
        if self.access_token and self.expires_at and time.time() < float(self.expires_at) - 60:
            return self.access_token
        if self.refresh():
            assert self.access_token
            return self.access_token
        if self.access_token:
            return self.access_token
        raise RuntimeError("Sin sesión. Debe iniciar sesión.")

    def prompt_login(self) -> None:
        from tray_ui import prompt_credentials, show_error

        creds = prompt_credentials()
        if not creds:
            raise RuntimeError("Inicio de sesión cancelado")
        email, password = creds
        try:
            self.login(email, password)
        except Exception as exc:
            show_error("Digitalizador Agent", str(exc))
            raise


def ensure_logged_in(base_url: str, session_path: Path) -> AgentSession:
    session = AgentSession(base_url, session_path)
    if session.has_tokens():
        try:
            session.ensure_access_token()
            # Validar contra pendientes (HEAD-like: GET sin docs)
            r = requests.get(
                f"{base_url.rstrip('/')}/api/public/agente/pendientes",
                headers={
                    "Authorization": f"Bearer {session.ensure_access_token()}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if r.status_code == 200:
                log.info("Sesión restaurada · %s", session.email or session.user_id)
                return session
            if r.status_code in (401, 403):
                log.warning("Sesión guardada inválida; debe volver a iniciar sesión")
                session.clear()
        except Exception as exc:
            log.warning("No se pudo reutilizar sesión: %s", exc)

    session.prompt_login()
    return session
