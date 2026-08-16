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
from ruat_flow import ContribuyenteYaRegistrado, DatosOcrInvalidos, RuatAutomator
from session_auth import SESSION_NAME, ensure_logged_in

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
        log.error("Copie .env.example a .env (solo hace falta BASE_URL)")
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    base = os.getenv("BASE_URL", "").rstrip("/") or "https://formflow-pro-sigma.vercel.app"
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

    dry = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    if not dry:
        try:
            ensure_playwright_firefox()
        except Exception:
            if is_frozen():
                input("Presione Enter para salir…")
            return 1

    try:
        session = ensure_logged_in(base, base_path / SESSION_NAME)
    except Exception as exc:
        log.error("No se pudo iniciar sesión: %s", exc)
        if is_frozen():
            input("Presione Enter para salir…")
        return 1

    api = AgenteApi(base, session)
    automator = RuatAutomator(download_dir=download)

    log.info(
        "Agente iniciado · %s · usuario=%s · poll=%ss · mode=%s · dir=%s",
        base,
        session.email or session.user_id,
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
                    if not automator.dry_run:
                        automator.ensure_connected()
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
                except DatosOcrInvalidos as datos:
                    log.warning("OCR inválido: %s", datos.mensaje)
                    api.resultado(doc_id, "error_automatizacion", datos.mensaje[:500])
                except Exception as exc:
                    log.exception("Error automatizando %s", doc_id)
                    msg = str(exc)
                    if "has been closed" in msg or "Target page" in msg or "browser has been closed" in msg:
                        msg = (
                            "Se perdio el control de Nightly. Cierre TODAS las ventanas Nightly, "
                            "inicie solo Digitalizador Agent, espere la Nightly que abre el agente, "
                            "inicie sesion RUAT ahi (no abra otra Nightly a mano) y vuelva a enviar."
                        )
                        try:
                            automator.ensure_connected()
                        except Exception as recon:
                            log.error("No se pudo reconectar Firefox: %s", recon)
                    try:
                        api.resultado(doc_id, "error_automatizacion", msg[:500])
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
