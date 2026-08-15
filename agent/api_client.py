from __future__ import annotations

import requests


class AgenteApi:
    """Auth por código de PC (x-computer-code). Sin token secreto."""

    def __init__(self, base_url: str, computer_code: str) -> None:
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-computer-code": computer_code.strip().upper(),
                "Accept": "application/json",
            }
        )

    def pendientes(self) -> dict:
        r = self.session.get(f"{self.base}/api/public/agente/pendientes", timeout=30)
        r.raise_for_status()
        return r.json()

    def resultado(self, document_id: str, estado: str, mensaje: str | None = None) -> dict:
        body = {"documentId": document_id, "estado": estado}
        if mensaje:
            body["mensaje"] = mensaje
        r = self.session.post(f"{self.base}/api/public/agente/resultado", json=body, timeout=30)
        r.raise_for_status()
        return r.json()
