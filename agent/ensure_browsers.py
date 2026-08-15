"""Instalación de Firefox de Playwright en el primer arranque (modo .exe)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from app_paths import browsers_dir, is_frozen

log = logging.getLogger("digitalizador-agent")


def _firefox_installed(target) -> bool:
    return any(target.glob("firefox*")) or any(target.glob("firefox-*"))


def ensure_playwright_firefox() -> None:
    """Define PLAYWRIGHT_BROWSERS_PATH e instala Firefox si falta."""
    target = browsers_dir()
    target.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(target)

    if _firefox_installed(target):
        return

    log.info("Primer arranque: instalando Firefox de Playwright en %s …", target)
    log.info("Puede tardar varios minutos (descarga única).")
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(target)}

    try:
        if is_frozen():
            from playwright._impl._driver import compute_driver_executable

            driver = compute_driver_executable()
            if isinstance(driver, (list, tuple)):
                cmd = [*map(str, driver), "install", "firefox"]
            else:
                cmd = [str(driver), "install", "firefox"]
            subprocess.run(cmd, check=True, env=env)
        else:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "firefox"],
                check=True,
                env=env,
            )
        log.info("Firefox de Playwright listo.")
    except Exception as exc:
        log.error("No se pudo instalar Firefox automáticamente: %s", exc)
        log.error("Revise permisos de escritura en %s", target)
        raise
