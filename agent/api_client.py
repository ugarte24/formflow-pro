from __future__ import annotations

from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from session_auth import AgentSession


class AgenteApi:
    """Auth por sesión de usuario (Bearer). Cola filtrada por operator_id en el servidor."""

    def __init__(self, base_url: str, session: AgentSession) -> None:
        self.base = base_url.rstrip("/")
        self.session_auth = session
        self.http = requests.Session()
        self.http.headers.update({"Accept": "application/json"})

    def _auth_headers(self) -> dict[str, str]:
        token = self.session_auth.ensure_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base}{path}"
        extra_headers = kwargs.pop("headers", None) or {}

        def once():
            headers = {**dict(self.http.headers), **self._auth_headers(), **extra_headers}
            return self.http.request(method, url, headers=headers, timeout=30, **kwargs)

        r = once()
        if r.status_code == 401:
            if self.session_auth.refresh():
                r = once()
            if r.status_code == 401:
                self.session_auth.clear()
                self.session_auth.prompt_login()
                r = once()
        r.raise_for_status()
        return r

    def pendientes(self) -> dict:
        return self._request("GET", "/api/public/agente/pendientes").json()

    def resultado(self, document_id: str, estado: str, mensaje: str | None = None) -> dict:
        body: dict = {"documentId": document_id, "estado": estado}
        if mensaje:
            body["mensaje"] = mensaje
        return self._request("POST", "/api/public/agente/resultado", json=body).json()
