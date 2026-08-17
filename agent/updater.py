"""Actualización automática del agente desde la web Digitalizador."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable

import requests

from app_paths import app_dir, is_frozen, resolve_data_file

log = logging.getLogger("digitalizador-agent")

ProgressCb = Callable[[str], None]


def local_version() -> str:
    for candidate in (
        app_dir() / "VERSION",
        resolve_data_file("VERSION"),
        Path(__file__).resolve().parent / "VERSION",
    ):
        try:
            if candidate.exists():
                v = candidate.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except OSError:
            continue
    return "0.0.0"


def _parse(v: str) -> tuple[int, int, int]:
    parts = (v.strip().split(".") + ["0", "0", "0"])[:3]
    out: list[int] = []
    for p in parts:
        try:
            out.append(int("".join(ch for ch in p if ch.isdigit()) or "0"))
        except ValueError:
            out.append(0)
    return out[0], out[1], out[2]


def is_newer(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


def fetch_update_info(base_url: str, timeout: float = 30) -> dict | None:
    url = f"{base_url.rstrip('/')}/api/public/agente/actualizacion"
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
        if r.status_code != 200:
            log.warning("Actualización: HTTP %s", r.status_code)
            return None
        data = r.json()
        if not data.get("disponible") or not data.get("url") or not data.get("version"):
            return None
        return data
    except Exception as exc:
        log.warning("No se pudo consultar actualización: %s", exc)
        return None


def _find_payload_root(extract_dir: Path) -> Path:
    """Localiza la carpeta que contiene DigitalizadorAgent.exe tras descomprimir."""
    direct = extract_dir / "DigitalizadorAgent.exe"
    if direct.exists():
        return extract_dir
    for exe in extract_dir.rglob("DigitalizadorAgent.exe"):
        return exe.parent
    raise RuntimeError("El paquete descargado no contiene DigitalizadorAgent.exe")


def download_and_stage(info: dict, progress: ProgressCb | None = None) -> Path:
    """Descarga el ZIP y lo extrae. Devuelve la carpeta con el .exe nuevo."""
    def report(msg: str) -> None:
        log.info(msg)
        if progress:
            progress(msg)

    url = str(info["url"])
    version = str(info["version"])
    work = Path(tempfile.mkdtemp(prefix="digitalizador-update-"))
    zip_path = work / f"setup-v{version}.zip"

    report(f"Descargando v{version}…")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if total and progress:
                    pct = min(99, int(done * 100 / total))
                    progress(f"Descargando v{version}… {pct}%")

    report("Descomprimiendo…")
    extract = work / "payload"
    extract.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract)

    root = _find_payload_root(extract)
    # Guardar meta para el script de actualización
    (work / "update-meta.json").write_text(
        json.dumps({"version": version, "payload": str(root), "work": str(work)}),
        encoding="utf-8",
    )
    return root


def apply_update_and_restart(
    payload_root: Path,
    *,
    progress: ProgressCb | None = None,
) -> None:
    """
    Lanza un .bat externo (vía WScript, independiente del proceso actual) que
    reemplaza archivos cuando este proceso ya salió, conserva .env / session.json /
    agent.log y reinicia el agente.
    """
    if not is_frozen():
        raise RuntimeError("La auto-actualización solo aplica al .exe instalado")

    dest = app_dir()
    exe_name = "DigitalizadorAgent.exe"
    new_exe = payload_root / exe_name
    if not new_exe.exists():
        raise RuntimeError("Paquete incompleto")

    def report(msg: str) -> None:
        log.info(msg)
        if progress:
            progress(msg)

    report("Preparando reinicio…")
    pid = os.getpid()
    tmp = Path(tempfile.gettempdir())
    bat = tmp / f"digitalizador-apply-update-{pid}.bat"
    vbs = tmp / f"digitalizador-apply-update-{pid}.vbs"
    log_file = tmp / "digitalizador-update.log"
    # Conservar configuración
    preserve = [".env", "session.json", "agent.log"]

    # Rutas con barras invertidas para cmd; comillas dobles escapadas en VBS
    dest_s = str(dest)
    src_s = str(payload_root)
    log_s = str(log_file)

    lines = [
        "@echo off",
        "setlocal EnableExtensions",
        f'set "DEST={dest_s}"',
        f'set "SRC={src_s}"',
        f'set "PID={pid}"',
        f'set "UPDLOG={log_s}"',
        'echo [%date% %time%] Inicio update PID=%PID% > "%UPDLOG%"',
        'echo DEST=%DEST%>> "%UPDLOG%"',
        'echo SRC=%SRC%>> "%UPDLOG%"',
        'echo Esperando cierre del agente...>> "%UPDLOG%"',
        ":wait",
        'tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >NUL",
        "  goto wait",
        ")",
        'echo Proceso principal cerrado.>> "%UPDLOG%"',
        "taskkill /F /IM DigitalizadorAgent.exe >NUL 2>&1",
        "timeout /t 3 /nobreak >NUL",
        'echo Copiando archivos nuevos...>> "%UPDLOG%"',
    ]
    for name in preserve:
        lines.append(
            f'if exist "%DEST%\\{name}" copy /Y "%DEST%\\{name}" "%TEMP%\\dig-keep-{name}" >NUL'
        )

    lines += [
        'robocopy "%SRC%" "%DEST%" /E /IS /IT /R:8 /W:2 /NFL /NDL /NJH /NJS /nc /ns /np >> "%UPDLOG%" 2>&1',
        "set RC=%ERRORLEVEL%",
        'echo robocopy RC=%RC%>> "%UPDLOG%"',
        "if %RC% GEQ 8 (",
        '  echo ERROR: robocopy fallo>> "%UPDLOG%"',
        "  exit /b 1",
        ")",
    ]
    for name in preserve:
        lines.append(
            f'if exist "%TEMP%\\dig-keep-{name}" copy /Y "%TEMP%\\dig-keep-{name}" "%DEST%\\{name}" >NUL'
        )

    lines += [
        f'if not exist "%DEST%\\{exe_name}" (',
        f'  echo ERROR: falta {exe_name} en DEST>> "%UPDLOG%"',
        "  exit /b 1",
        ")",
        "timeout /t 1 /nobreak >NUL",
        'echo Reiniciando agente...>> "%UPDLOG%"',
        f'start "" /D "%DEST%" "%DEST%\\{exe_name}"',
        'echo Listo.>> "%UPDLOG%"',
        "endlocal",
        'del "%~f0" >NUL 2>&1',
    ]
    bat.write_text("\r\n".join(lines) + "\r\n", encoding="ascii", errors="replace")

    # WScript.Run(..., 0, False) = oculto y sin esperar: sobrevive al cierre del agente
    # (CREATE_NO_WINDOW|DETACHED_PROCESS a menudo muere con el job del .exe).
    # En VBS, "" dentro de un string es una comilla literal → cmd /c "ruta\al.bat"
    vbs.write_text(
        "\r\n".join(
            [
                'Set sh = CreateObject("WScript.Shell")',
                # VBS: "" = comilla; resultado → cmd.exe /c "ruta\al.bat"
                f'sh.Run "cmd.exe /c ""{bat}""", 0, False',
            ]
        )
        + "\r\n",
        encoding="ascii",
        errors="replace",
    )

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | 0x00000200  # CREATE_NEW_PROCESS_GROUP
            | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
        )

    subprocess.Popen(
        ["wscript.exe", "//B", "//Nologo", str(vbs)],
        cwd=str(tmp),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=False,
        creationflags=creationflags,
    )
    log.info("Script de actualización lanzado (%s); log=%s", bat, log_file)
    time.sleep(0.6)


def check_and_update(
    base_url: str,
    *,
    auto: bool,
    progress: ProgressCb | None = None,
    ask: Callable[[str, str], bool] | None = None,
) -> bool:
    """
    Consulta versión remota. Si hay nueva y (auto o ask confirma), descarga y reinicia.
    Devuelve True si se inició el proceso de actualización (el proceso debe salir).
    """
    local = local_version()
    info = fetch_update_info(base_url)
    if not info:
        return False
    remote = str(info["version"])
    if not is_newer(remote, local):
        log.info("Agente al día (local=%s remote=%s)", local, remote)
        return False

    msg = f"Hay una versión nueva: v{remote} (actual: v{local})."
    log.info(msg)
    if not auto:
        if ask and not ask("Actualización disponible", f"{msg}\n\n¿Descargar e instalar ahora?"):
            return False
        if not ask:
            return False

    if not is_frozen():
        log.warning("Omitiendo auto-update en modo desarrollo")
        return False

    payload = download_and_stage(info, progress=progress)
    apply_update_and_restart(payload, progress=progress)
    return True
