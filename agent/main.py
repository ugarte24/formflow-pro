"""Digitalizador Agent — polling + orquestación RUAT."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from api_client import AgenteApi
from app_paths import app_dir, is_frozen
from ensure_browsers import ensure_playwright_firefox
from ruat_flow import ContribuyenteYaRegistrado, RuatAutomator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("digitalizador-agent")


def main() -> int:
    base_path = app_dir()
    env_path = base_path / ".env"
    load_dotenv(env_path)

    if not env_path.exists():
        log.error("Falta el archivo .env junto al programa: %s", env_path)
        log.error("Copie .env.example a .env y complete BASE_URL + CODIGO_PC")
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    base = os.getenv("BASE_URL", "").rstrip("/")
    # Preferido: código de PC (sin token). Compat: AGENT_TOKEN legado.
    codigo = (os.getenv("CODIGO_PC") or os.getenv("COMPUTER_CODE") or "").strip().upper()
    token_legado = os.getenv("AGENT_TOKEN", "").strip()
    poll = float(os.getenv("POLL_SECONDS", "4"))
    download = Path(
        os.path.expandvars(os.getenv("DOWNLOAD_DIR", r"%USERPROFILE%\DigitalizadorAgent\downloads"))
    )
    download.mkdir(parents=True, exist_ok=True)

    if not base:
        log.error("Configure BASE_URL en %s", env_path)
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    if not codigo and not (token_legado and len(token_legado) >= 20):
        log.error("Configure CODIGO_PC en %s (ej. PC-VEN-01). Ya no se usa token.", env_path)
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    dry = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    if not dry:
        try:
            ensure_playwright_firefox()
        except Exception:
            if is_frozen():
                input("Presione Enter para salir…")
            return 1

    if codigo:
        api = AgenteApi(base, codigo)
        log.info("Auth por código de PC: %s", codigo)
    else:
        # Compatibilidad temporal con instalaciones viejas
        from requests import Session

        class _Legacy:
            def __init__(self) -> None:
                self.session = Session()
                self.session.headers.update(
                    {"x-agent-token": token_legado, "Accept": "application/json"}
                )
                self.base = base

            def pendientes(self) -> dict:
                r = self.session.get(f"{self.base}/api/public/agente/pendientes", timeout=30)
                r.raise_for_status()
                return r.json()

            def resultado(self, document_id: str, estado: str, mensaje: str | None = None) -> dict:
                body = {"documentId": document_id, "estado": estado}
                if mensaje:
                    body["mensaje"] = mensaje
                r = self.session.post(
                    f"{self.base}/api/public/agente/resultado", json=body, timeout=30
                )
                r.raise_for_status()
                return r.json()

        api = _Legacy()  # type: ignore[assignment]
        log.warning("Usando AGENT_TOKEN legado — migre a CODIGO_PC")

    automator = RuatAutomator(download_dir=download)

    log.info(
        "Agente iniciado · %s · poll=%ss · mode=%s · dir=%s",
        base,
        poll,
        automator.mode,
        base_path,
    )
    if automator.dry_run:
        log.warning("DRY_RUN activo: no interactúa con Firefox, solo reporta pendientes")

    try:
        if not automator.dry_run:
            automator.connect()
    except Exception as exc:
        log.error("No se pudo conectar a Firefox/Playwright: %s", exc)
        log.error("Verifique la instalación de Firefox (primer arranque) o FIREFOX_MODE")
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    while True:
        try:
            payload = api.pendientes()
            docs = payload.get("documentos") or []
            if not docs:
                time.sleep(poll)
                continue

            for doc in docs:
                doc_id = doc["id"]
                log.info("Procesando %s · CI %s", doc_id, doc.get("numero_documento"))
                try:
                    automator.procesar(doc)
                    api.resultado(
                        doc_id,
                        "formulario_completado",
                        "Revise el Reporte de Control de Datos con el contribuyente y luego pulse Grabar en RUAT. El agente no guardó el trámite.",
                    )
                    log.info("OK %s — operador debe revisar reporte y Grabar", doc_id)
                except ContribuyenteYaRegistrado as ya:
                    log.warning("CI ya registrado: %s", ya.mensaje)
                    api.resultado(doc_id, "error_automatizacion", ya.mensaje[:500])
                except Exception as exc:
                    log.exception("Error automatizando %s", doc_id)
                    try:
                        api.resultado(doc_id, "error_automatizacion", str(exc)[:500])
                    except Exception as report_exc:
                        log.error("No se pudo reportar error: %s", report_exc)
        except KeyboardInterrupt:
            log.info("Detenido por el usuario")
            break
        except Exception as exc:
            log.error("Error de ciclo: %s", exc)
            time.sleep(poll)

    if not automator.dry_run:
        automator.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
