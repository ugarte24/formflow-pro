"""
Inspecciona la página RUAT actual y lista labels, inputs, botones y links.
Úsalo para completar agent/selectors.json.

Uso (con el mismo .env que el agente):
  python inspect_page.py
  python inspect_page.py --url "https://..."
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ruat_flow import RuatAutomator


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Inspeccionar HTML RUAT para calibrar selectors.json")
    parser.add_argument("--url", default=os.getenv("RUAT_START_URL", ""), help="URL opcional a abrir")
    parser.add_argument(
        "--wait",
        type=int,
        default=20,
        help="Segundos para que navegues manualmente antes de inspeccionar",
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
    print(f"Espera {args.wait}s: navega a la pantalla que quieras inspeccionar, luego no toques nada…\n")
    page.wait_for_timeout(args.wait * 1000)

    print("=" * 60)
    print("URL:", page.url)
    print("Título:", page.title())
    print("=" * 60)

    print("\n--- LINKS (texto) ---")
    for el in page.get_by_role("link").all()[:40]:
        try:
            t = (el.inner_text() or "").strip().replace("\n", " ")
            if t:
                print(f"  link: {t[:120]}")
        except Exception:
            pass

    print("\n--- BOTONES ---")
    for el in page.get_by_role("button").all()[:40]:
        try:
            t = (el.inner_text() or el.get_attribute("value") or "").strip().replace("\n", " ")
            if t:
                print(f"  button: {t[:120]}")
        except Exception:
            pass

    print("\n--- LABELS ---")
    for el in page.locator("label").all()[:50]:
        try:
            t = (el.inner_text() or "").strip().replace("\n", " ")
            fr = el.get_attribute("for") or ""
            if t:
                print(f"  label: {t[:80]}  for={fr}")
        except Exception:
            pass

    print("\n--- INPUTS ---")
    for el in page.locator("input").all()[:50]:
        try:
            tipo = el.get_attribute("type") or "text"
            name = el.get_attribute("name") or ""
            iid = el.get_attribute("id") or ""
            ph = el.get_attribute("placeholder") or ""
            print(f"  input type={tipo} name={name} id={iid} placeholder={ph}")
        except Exception:
            pass

    print("\n--- SELECTS ---")
    for el in page.locator("select").all()[:20]:
        try:
            name = el.get_attribute("name") or ""
            iid = el.get_attribute("id") or ""
            opts = el.locator("option").all_text_contents()[:8]
            print(f"  select name={name} id={iid} options={opts}")
        except Exception:
            pass

    print("\n--- FILE INPUTS ---")
    n = page.locator("input[type='file']").count()
    print(f"  cantidad: {n}")

    print("\nListo. Copia los textos exactos a selectors.json (nombres de botones/labels).")
    print("Enter para cerrar…")
    try:
        input()
    except EOFError:
        pass
    bot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
