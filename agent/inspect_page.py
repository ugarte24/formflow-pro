"""
Inspecciona la página RUAT actual (página + iframes) y guarda un dump JSON
para calibrar agent/selectors.json.

Uso (con el mismo .env que el agente):
  python inspect_page.py
  python inspect_page.py --url "http://municipios.ruat.net/..."
  python inspect_page.py --wait 30 --no-connect
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from ruat_flow import RuatAutomator


def _dump_scope(scope, label: str) -> dict:
    """Extrae controles de un Page o Frame."""
    data: dict = {
        "label": label,
        "url": "",
        "links": [],
        "buttons": [],
        "labels": [],
        "inputs": [],
        "selects": [],
        "file_inputs": 0,
        "checkboxes": [],
    }
    try:
        data["url"] = getattr(scope, "url", None) or ""
    except Exception:
        pass

    try:
        for el in scope.get_by_role("link").all()[:60]:
            try:
                t = (el.inner_text(timeout=400) or "").strip().replace("\n", " ")
                if t:
                    data["links"].append(t[:160])
            except Exception:
                pass
    except Exception:
        pass

    try:
        for el in scope.locator(
            "button, input[type='submit'], input[type='button']"
        ).all()[:60]:
            try:
                t = (
                    el.inner_text(timeout=400)
                    or el.get_attribute("value")
                    or ""
                ).strip().replace("\n", " ")
                if t:
                    data["buttons"].append(t[:160])
            except Exception:
                pass
    except Exception:
        pass

    try:
        for el in scope.locator("label").all()[:80]:
            try:
                t = (el.inner_text(timeout=400) or "").strip().replace("\n", " ")
                fr = el.get_attribute("for") or ""
                if t:
                    data["labels"].append({"text": t[:120], "for": fr})
            except Exception:
                pass
    except Exception:
        pass

    try:
        for el in scope.locator("input").all()[:80]:
            try:
                tipo = el.get_attribute("type") or "text"
                name = el.get_attribute("name") or ""
                iid = el.get_attribute("id") or ""
                ph = el.get_attribute("placeholder") or ""
                entry = {
                    "type": tipo,
                    "name": name,
                    "id": iid,
                    "placeholder": ph,
                }
                data["inputs"].append(entry)
                if (tipo or "").lower() == "checkbox":
                    data["checkboxes"].append(entry)
                if (tipo or "").lower() == "file":
                    data["file_inputs"] += 1
            except Exception:
                pass
    except Exception:
        pass

    try:
        for el in scope.locator("select").all()[:30]:
            try:
                name = el.get_attribute("name") or ""
                iid = el.get_attribute("id") or ""
                opts = el.locator("option").all_text_contents()[:12]
                data["selects"].append({"name": name, "id": iid, "options": opts})
            except Exception:
                pass
    except Exception:
        pass

    return data


def _print_scope(dump: dict) -> None:
    print("\n" + "=" * 60)
    print(f"SCOPE: {dump.get('label')}  url={dump.get('url', '')[:100]}")
    print("=" * 60)
    print("\n--- LINKS ---")
    for t in dump.get("links") or []:
        print(f"  link: {t}")
    print("\n--- BOTONES ---")
    for t in dump.get("buttons") or []:
        print(f"  button: {t}")
    print("\n--- LABELS ---")
    for lab in dump.get("labels") or []:
        print(f"  label: {lab.get('text')}  for={lab.get('for')}")
    print("\n--- INPUTS ---")
    for inp in dump.get("inputs") or []:
        print(
            f"  input type={inp.get('type')} name={inp.get('name')} "
            f"id={inp.get('id')} placeholder={inp.get('placeholder')}"
        )
    print("\n--- SELECTS ---")
    for sel in dump.get("selects") or []:
        print(f"  select name={sel.get('name')} id={sel.get('id')} options={sel.get('options')}")
    print(f"\n--- FILE INPUTS: {dump.get('file_inputs', 0)} ---")


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Inspeccionar HTML RUAT (con frames) para calibrar selectors.json")
    parser.add_argument("--url", default=os.getenv("RUAT_START_URL", ""), help="URL opcional a abrir")
    parser.add_argument(
        "--wait",
        type=int,
        default=20,
        help="Segundos para navegar manualmente antes de inspeccionar",
    )
    parser.add_argument(
        "--pantalla",
        default="",
        help="Código de pantalla para el nombre del dump (ej. datos_generales)",
    )
    args = parser.parse_args()

    if args.url:
        os.environ["RUAT_START_URL"] = args.url

    download = Path(
        os.path.expandvars(os.getenv("DOWNLOAD_DIR", r"%USERPROFILE%\DigitalizadorAgent\downloads"))
    )
    download.mkdir(parents=True, exist_ok=True)
    bot = RuatAutomator(download_dir=download)

    print("Conectando Firefox…")
    bot.connect()
    assert bot.page is not None
    page = bot.page

    print(f"\nURL actual: {page.url}")
    print(f"Espera {args.wait}s: navega a la pantalla a inspeccionar…\n")
    page.wait_for_timeout(args.wait * 1000)

    page = bot._page_activa()
    pant = bot.identificar_pantalla(page)
    codigo = (args.pantalla or pant or "desconocida").strip()
    print(f"Pantalla detectada: {pant} → dump como «{codigo}»")

    scopes_dump = []
    # Página principal
    scopes_dump.append(_dump_scope(page, "page"))
    # Frames
    try:
        for i, fr in enumerate(page.frames):
            if fr == page.main_frame:
                scopes_dump.append(_dump_scope(fr, "main_frame"))
                continue
            name = ""
            try:
                name = fr.name or ""
            except Exception:
                pass
            scopes_dump.append(_dump_scope(fr, f"frame[{i}]{(':' + name) if name else ''}"))
    except Exception as exc:
        print(f"Error listando frames: {exc}")

    for d in scopes_dump:
        _print_scope(d)

    dumps_dir = Path(__file__).with_name("dumps")
    dumps_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = dumps_dir / f"pantalla-{codigo}-{ts}.json"
    payload = {
        "pantalla_detectada": pant,
        "codigo": codigo,
        "page_url": page.url,
        "timestamp": ts,
        "scopes": scopes_dump,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDump guardado: {out}")
    print("Copiá name/id estables a selectors.json.")
    print("Enter para cerrar…")
    try:
        input()
    except EOFError:
        pass
    bot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
