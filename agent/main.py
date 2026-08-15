"""Digitalizador Agent — polling + orquestación RUAT."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from api_client import AgenteApi
from ruat_flow import ContribuyenteYaRegistrado, RuatAutomator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("digitalizador-agent")


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    base = os.getenv("BASE_URL", "").rstrip("/")
    token = os.getenv("AGENT_TOKEN", "").strip()
    poll = float(os.getenv("POLL_SECONDS", "4"))
    download = Path(
        os.path.expandvars(os.getenv("DOWNLOAD_DIR", r"%USERPROFILE%\DigitalizadorAgent\downloads"))
    )
    download.mkdir(parents=True, exist_ok=True)

    if not base or len(token) < 20:
        log.error("Configure BASE_URL y AGENT_TOKEN en agent/.env (vea .env.example)")
        return 1

    api = AgenteApi(base, token)
    automator = RuatAutomator(download_dir=download)

    log.info("Agente iniciado · %s · poll=%ss · mode=%s", base, poll, automator.mode)
    if automator.dry_run:
        log.warning("DRY_RUN activo: no interactúa con Firefox, solo reporta pendientes")

    try:
        if not automator.dry_run:
            automator.connect()
    except Exception as exc:
        log.error("No se pudo conectar a Firefox/Playwright: %s", exc)
        log.error("Ejecute: playwright install firefox")
        log.error("O use FIREFOX_MODE=connect_cdp con start-firefox-ruat.ps1")
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
