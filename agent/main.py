"""Digitalizador Agent — ventana + bandeja + auto-actualización."""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from agent_ui import AgentWindow, run_startup_update
from api_client import AgenteApi
from app_paths import app_dir, is_frozen, resolve_data_file
from ensure_browsers import ensure_playwright_firefox
from ruat_flow import ContribuyenteYaRegistrado, DatosOcrInvalidos, RuatAutomator
from session_auth import SESSION_NAME, ensure_logged_in
from tray_ui import show_error
from updater import local_version

log = logging.getLogger("digitalizador-agent")


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if not is_frozen() and sys.stderr and hasattr(sys.stderr, "write"):
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)


def main() -> int:
    base_path = app_dir()
    log_path = base_path / "agent.log"
    setup_logging(log_path)

    env_path = base_path / ".env"
    load_dotenv(env_path)

    if not env_path.exists():
        msg = f"Falta el archivo .env junto al programa:\n{env_path}\n\nCopie .env.example a .env (solo BASE_URL)."
        log.error(msg)
        show_error("Digitalizador Agent", msg)
        return 1

    base = os.getenv("BASE_URL", "").rstrip("/") or "https://formflow-pro-sigma.vercel.app"
    poll = float(os.getenv("POLL_SECONDS", "4"))
    download = Path(
        os.path.expandvars(os.getenv("DOWNLOAD_DIR", r"%USERPROFILE%\DigitalizadorAgent\downloads"))
    )
    download.mkdir(parents=True, exist_ok=True)

    if not base:
        show_error("Digitalizador Agent", f"Configure BASE_URL en:\n{env_path}")
        return 1

    # Auto-update al iniciar (antes de login / Firefox)
    try:
        if run_startup_update(base):
            log.info("Saliendo para aplicar actualización…")
            # Salida forzada para no bloquear el .bat de copia/reinicio
            os._exit(0)
    except Exception as exc:
        log.warning("Auto-update omitido: %s", exc)

    dry = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    if not dry:
        try:
            ensure_playwright_firefox()
        except Exception as exc:
            show_error(
                "Digitalizador Agent",
                f"No se pudo preparar Firefox de Playwright.\n{exc}",
            )
            return 1

    try:
        session = ensure_logged_in(base, base_path / SESSION_NAME)
    except Exception as exc:
        log.error("No se pudo iniciar sesión: %s", exc)
        if "cancelado" not in str(exc).lower():
            show_error("Digitalizador Agent", f"No se pudo iniciar sesión:\n{exc}")
        return 1

    api = AgenteApi(base, session)
    automator = RuatAutomator(download_dir=download)
    status = {"text": "Iniciando…"}
    stop = threading.Event()
    fatal = {"msg": None}
    # El operador abre RUAT, inicia sesión y pulsa «Iniciar» en el agente
    start_requested = threading.Event()
    flow_ready = threading.Event()

    log.info(
        "Agente iniciado · v%s · %s · usuario=%s · poll=%ss · mode=%s",
        local_version(),
        base,
        session.email or session.user_id,
        poll,
        automator.mode,
    )
    if automator.dry_run:
        log.warning("DRY_RUN activo: no interactúa con Firefox, solo reporta pendientes")

    def worker() -> None:
        # Playwright sync DEBE vivir solo en este hilo (evita greenlet "Cannot switch thread")
        try:
            if not automator.dry_run:
                status["text"] = "Abriendo Firefox del agente…"
                automator.connect()
                status["text"] = (
                    "Abra municipios.ruat.net, inicie sesión, deje el MENÚ PRINCIPAL "
                    "visible y pulse «Iniciar»."
                )
            else:
                flow_ready.set()
                status["text"] = "Esperando trámites… (DRY_RUN)"
        except Exception as exc:
            log.error("No se pudo conectar a Firefox/Playwright: %s", exc)
            fatal["msg"] = str(exc)
            status["text"] = "Error al abrir Firefox"
            stop.set()
            return

        while not stop.is_set():
            try:
                # Esperar confirmación del operador (menú RUAT listo)
                if not automator.dry_run and not flow_ready.is_set():
                    status["text"] = (
                        "Espere: menú principal RUAT visible → pulse «Iniciar»"
                    )
                    if start_requested.wait(timeout=1.0):
                        start_requested.clear()
                        try:
                            automator.ensure_connected()
                            if automator.menu_principal_listo():
                                flow_ready.set()
                                status["text"] = (
                                    "Listo — esperando trámites… "
                                    "(menú RUAT verificado)"
                                )
                                log.info("Operador confirmó Iniciar — menú RUAT OK")
                            else:
                                motivo = automator.motivo_menu_no_listo()
                                status["text"] = f"No listo: {motivo}"
                                log.warning("Iniciar rechazado: %s", motivo)
                        except Exception as exc:
                            status["text"] = f"No se pudo verificar RUAT: {exc}"
                            log.warning("Verificación menú falló: %s", exc)
                    continue

                payload = api.pendientes()
                docs = payload.get("documentos") or []
                if not docs:
                    if flow_ready.is_set():
                        status["text"] = (
                            "Esperando trámites… Menú RUAT listo "
                            "(Contribuyente Natural → Registro)"
                        )
                    stop.wait(poll)
                    continue

                for doc in docs:
                    if stop.is_set():
                        break
                    if not automator.dry_run and not flow_ready.is_set():
                        break
                    doc_id = doc["id"]
                    ci = doc.get("numero_documento") or "?"
                    status["text"] = f"Procesando CI {ci}"
                    log.info("Procesando %s · CI %s", doc_id, ci)
                    try:
                        if not automator.dry_run:
                            automator.ensure_connected()
                            if not automator.menu_principal_listo():
                                pant = automator.identificar_pantalla(automator._page_activa())
                                # Permitir si ya está en flujo de alta
                                if pant not in (
                                    "submenu_contribuyente_natural",
                                    "buscar",
                                    "resultados_busqueda",
                                    "recepcionar",
                                    "datos_generales",
                                    "domicilio",
                                    "info_adicional",
                                    "imagenes",
                                    "confirmar",
                                ):
                                    flow_ready.clear()
                                    raise RuntimeError(automator.motivo_menu_no_listo())
                        automator.procesar(doc)
                        api.resultado(
                            doc_id,
                            "formulario_completado",
                            "Revise el Reporte de Control de Datos con el contribuyente y luego pulse Grabar en RUAT. El agente no guardó el trámite.",
                        )
                        log.info("OK %s — operador debe revisar reporte y Grabar", doc_id)
                        status["text"] = f"Listo CI {ci} — revise Grabar en RUAT"
                    except ContribuyenteYaRegistrado as ya:
                        log.warning("CI ya registrado: %s", ya.mensaje)
                        api.resultado(doc_id, "error_automatizacion", ya.mensaje[:500])
                        status["text"] = f"CI {ci} ya registrado"
                    except DatosOcrInvalidos as datos:
                        log.warning("OCR inválido: %s", datos.mensaje)
                        api.resultado(doc_id, "error_automatizacion", datos.mensaje[:500])
                        status["text"] = f"OCR inválido CI {ci}"
                    except Exception as exc:
                        log.exception("Error automatizando %s", doc_id)
                        msg = str(exc)
                        paso = getattr(automator, "_paso_actual", "?")
                        pant = getattr(automator, "_ultima_pantalla", "?")
                        if "greenlet" in msg.lower() or "Cannot switch" in msg:
                            msg = (
                                "Error interno de hilos del agente. Actualice a la última versión "
                                "y reinicie Digitalizador Agent."
                            )
                        elif "has been closed" in msg or "Target page" in msg or "browser has been closed" in msg:
                            msg = (
                                "Se perdio el control de Firefox. Cierre ventanas extras, "
                                "deje solo la del agente con el menú RUAT e inicie sesión ahí."
                            )
                            flow_ready.clear()
                            try:
                                automator.ensure_connected()
                            except Exception as recon:
                                log.error("No se pudo reconectar Firefox: %s", recon)
                        else:
                            if "Paso «" not in msg and "pantalla=" not in msg.lower():
                                msg = (
                                    f"Paso «{paso}» (pantalla={pant}): {msg}. "
                                    "Cierre el trámite a medias en RUAT o vuelva al menú y use Reintentar envío."
                                )
                        try:
                            api.resultado(doc_id, "error_automatizacion", msg[:500])
                        except Exception as report_exc:
                            log.error("No se pudo reportar error: %s", report_exc)
                        status["text"] = f"Error CI {ci} · {paso}"
            except Exception as exc:
                if stop.is_set():
                    break
                log.error("Error de ciclo: %s", exc)
                status["text"] = "Error de conexión — reintentando…"
                stop.wait(poll)

        try:
            if not automator.dry_run:
                automator.close()
        except Exception:
            pass
        log.info("Worker detenido")

    t = threading.Thread(target=worker, name="agent-worker", daemon=True)
    t.start()

    # Si Firefox falló al arrancar, avisar en el hilo de UI
    def _check_fatal() -> None:
        if fatal["msg"]:
            show_error(
                "Digitalizador Agent",
                "No se pudo conectar a Firefox/Playwright.\n"
                "Verifique la instalación o FIREFOX_MODE.\n\n"
                f"{fatal['msg']}",
            )

    ico = resolve_data_file("DigitalizadorAgent.ico")
    user_label = session.email or session.nombre or session.user_id or "—"

    def on_quit() -> None:
        stop.set()
        start_requested.set()  # despertar wait
        status["text"] = "Saliendo…"

    def on_logout() -> None:
        session.clear()
        log.info("Sesión cerrada por el usuario")

    def on_iniciar() -> None:
        """El operador confirma que el menú RUAT está listo."""
        if fatal["msg"]:
            show_error("Digitalizador Agent", f"Firefox no está listo:\n{fatal['msg']}")
            return
        start_requested.set()
        status["text"] = "Verificando menú RUAT…"

    def on_pausar() -> None:
        flow_ready.clear()
        status["text"] = "Pausado — pulse «Iniciar» cuando el menú RUAT esté visible"

    win = AgentWindow(
        base_url=base,
        user_label=user_label,
        status_fn=lambda: status["text"],
        log_path=log_path,
        app_dir=base_path,
        ico_path=ico if ico.exists() else None,
        on_quit=on_quit,
        on_logout=on_logout,
        on_iniciar=on_iniciar,
        on_pausar=on_pausar,
    )
    # Dar un momento al worker para conectar / fallar
    threading.Timer(2.5, _check_fatal).start()
    try:
        win.run()
    finally:
        stop.set()
        t.join(timeout=8)

    return 0


if __name__ == "__main__":
    sys.exit(main())
