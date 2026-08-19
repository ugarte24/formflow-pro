"""
Automatización RUAT — Registro Contribuyente Natural.

Modos de Firefox (FIREFOX_MODE):
  - persistent (recomendado): reutiliza un perfil donde el operador ya inició sesión RUAT
  - connect_cdp: se adjunta a Firefox ya abierto con --remote-debugging-port
  - launch: abre Firefox limpio (solo pruebas; pierde sesión/IP)

Selectores: agent/selectors.json (ajustables sin tocar código).
Modo seguro: completa hasta dejar listo; no hace el guardado final del trámite.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

log = logging.getLogger("ruat")

SELECTORS_PATH = Path(__file__).with_name("selectors.json")

# Entrada fija del agente (menú principal Contribuyentes — municipios.ruat.net)
RUAT_MENU_DEFAULT = (
    "http://municipios.ruat.net/ContribuyentesWeb/Administracion/menuPrincipal/MenuPrincipalController.jpf"
)
RUAT_HOST_HINT = "municipios.ruat.net"


class ContribuyenteYaRegistrado(Exception):
    """CI ya existe en el mismo municipio (ej. RIBERALTA): no continuar el alta."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class DatosOcrInvalidos(Exception):
    """Género, estado civil o fecha vacíos/raros: avisar al operador."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


def _load_selectors() -> dict[str, Any]:
    try:
        from app_paths import resolve_data_file

        path = resolve_data_file("selectors.json")
    except Exception:
        path = SELECTORS_PATH
    if not path.exists():
        log.warning("No hay selectors.json — se usan valores por defecto embebidos")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class RuatAutomator:
    def __init__(self, download_dir: Path) -> None:
        self.download_dir = download_dir
        self.selectors = _load_selectors()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None
        self.dry_run = os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
        self.ruat_url = (os.getenv("RUAT_START_URL", "").strip() or RUAT_MENU_DEFAULT)
        self.mode = (os.getenv("FIREFOX_MODE") or "persistent").strip().lower()
        self._paso_actual = "idle"
        self._ultima_pantalla = "desconocida"

    def connect(self) -> None:
        self._pw = sync_playwright().start()
        if self.mode == "connect_cdp":
            self._connect_cdp()
        elif self.mode == "launch":
            self._connect_launch()
        else:
            self._connect_persistent()

        assert self.page is not None
        # Diálogos nativos: Cancelar si preguntan por Apoderado (también en pestañas nuevas)
        if self._context is not None:
            self._context.on("page", lambda p: p.on("dialog", self._on_browser_dialog))
        self.page.on("dialog", self._on_browser_dialog)
        # NO navegar a RUAT: el operador abre municipios.ruat.net e inicia sesión.
        self._seleccionar_pestana_existente()
        log.info(
            "Firefox listo (sin forzar URL) · mode=%s · url=%s",
            self.mode,
            (self.page.url if self.page else "") or "—",
        )

    def _seleccionar_pestana_existente(self) -> None:
        """Elige la mejor pestaña abierta; no hace goto a municipios.ruat.net."""
        if self._context is None:
            return
        try:
            self.page = self._pick_page(self._context)
        except Exception:
            pass
        # Cerrar about:blank extras si ya hay una pestaña RUAT
        try:
            pages = [p for p in self._context.pages if not p.is_closed()]
            has_ruat = any(RUAT_HOST_HINT in ((p.url or "").lower()) for p in pages)
            if has_ruat:
                for p in pages:
                    if p == self.page:
                        continue
                    u = (p.url or "").lower()
                    if u in ("", "about:blank", "about:newtab"):
                        try:
                            p.close()
                        except Exception:
                            pass
                self.page = self._pick_page(self._context)
        except Exception:
            pass

    def menu_principal_listo(self) -> bool:
        """True si la ventana muestra el menú principal RUAT (sesión ya iniciada)."""
        try:
            page = self._page_activa()
            pant = self.identificar_pantalla(page)
            if pant == "menu_principal":
                return True
            if pant == "login_ruat":
                return False
            # Menú con columna REGISTRO CONTRIBUYENTES
            if self._hay_contribuyente_natural_menu(page):
                return True
            url = (page.url or "").lower()
            texto = self._page_text(page)
            if RUAT_HOST_HINT in url and "contribuyente natural" in texto and "cerrar sesión" in texto:
                return True
            if RUAT_HOST_HINT in url and "registro contribuyentes" in texto:
                return True
            return False
        except Exception:
            return False

    def motivo_menu_no_listo(self) -> str:
        """Mensaje corto si aún no se puede iniciar el flujo."""
        try:
            page = self._page_activa()
            pant = self.identificar_pantalla(page)
            url = (page.url or "").strip()
            if pant == "login_ruat":
                return "RUAT pide inicio de sesión. Inicie sesión y deje el menú principal visible."
            if not url or url.startswith("about:"):
                return (
                    "No hay página RUAT abierta. En la ventana del agente abra "
                    "municipios.ruat.net, inicie sesión y deje el menú principal."
                )
            if RUAT_HOST_HINT not in url.lower():
                return (
                    f"La pestaña no es RUAT ({url[:60]}). Abra el menú principal "
                    "de Contribuyentes e inicie sesión."
                )
            return (
                f"Veo RUAT pero no el menú principal (pantalla={pant}). "
                "Pulse «Menú Principal» en RUAT y luego Iniciar."
            )
        except Exception as exc:
            return f"No se pudo leer el navegador: {exc}"

    def _abrir_ruat_al_inicio(self) -> None:
        """Obsoleto: ya no se navega automáticamente. Conservado por compatibilidad."""
        self._seleccionar_pestana_existente()

    @staticmethod
    def _on_browser_dialog(dialog) -> None:
        msg = dialog.message or ""
        log.info("Diálogo navegador: %s", msg[:200])
        if re.search(r"Apoderado|Representante\s*Legal", msg, re.I):
            dialog.dismiss()  # Cancelar
            log.info("Apoderado → Cancelar (dismiss)")
        else:
            # Por defecto no aceptar confirmaciones inesperadas
            dialog.dismiss()
            log.warning("Diálogo no esperado → dismiss")

    def _connect_persistent(self) -> None:
        assert self._pw is not None
        profile = Path(
            os.path.expandvars(
                os.getenv(
                    "FIREFOX_PROFILE_DIR",
                    r"%USERPROFILE%\DigitalizadorAgent\firefox-profile",
                )
            )
        )
        profile.mkdir(parents=True, exist_ok=True)
        self._context = self._pw.firefox.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1366, "height": 900},
            # Sin homepage forzada: el operador abre RUAT e inicia sesión.
        )
        self.page = self._pick_page(self._context)
        log.info(
            "Perfil persistente: %s — inicie sesión RUAT una vez en esta ventana si aún no lo hizo",
            profile,
        )

    def _connect_cdp(self) -> None:
        assert self._pw is not None
        endpoint = os.getenv("FIREFOX_CDP_URL", "http://127.0.0.1:9222").strip()
        # Firefox 129+ expone CDP con --remote-debugging-port=9222
        self._browser = self._pw.firefox.connect_over_cdp(endpoint)
        contexts = self._browser.contexts
        if not contexts:
            raise RuntimeError(
                f"No hay contextos en {endpoint}. Abra Firefox con "
                f"--remote-debugging-port=9222 y la sesión RUAT activa."
            )
        self._context = contexts[0]
        self.page = self._pick_page(self._context)
        log.info("Conectado por CDP a %s", endpoint)

    def _connect_launch(self) -> None:
        assert self._pw is not None
        self._browser = self._pw.firefox.launch(headless=False)
        self._context = self._browser.new_context(accept_downloads=True)
        self.page = self._context.new_page()
        log.warning(
            "FIREFOX_MODE=launch abre un perfil vacío. Preferible persistent o connect_cdp "
            "para conservar sesión e IP autorizada."
        )

    def _page_text(self, page: Page) -> str:
        """Texto visible incluyendo iframes (misma ventana; RUAT a veces usa frames)."""
        parts: list[str] = []
        try:
            parts.append(page.locator("body").inner_text(timeout=600) or "")
        except Exception:
            pass
        try:
            for fr in page.frames:
                if fr == page.main_frame:
                    continue
                try:
                    parts.append(fr.locator("body").inner_text(timeout=400) or "")
                except Exception:
                    continue
        except Exception:
            pass
        return " ".join(parts)[:8000].lower()

    def _page_score(self, page: Page) -> int:
        """Puntúa si la pestaña tiene UI RUAT útil (misma ventana, distinto layout)."""
        try:
            if page.is_closed():
                return -1
            url = (page.url or "").strip().lower()
            if not url or url.startswith("about:"):
                return 0
            score = 1
            if "ruat" in url or "municipios" in url or "contribuyentes" in url:
                score += 15
            if "armadosubmenu" in url or "submenu" in url:
                score += 55
            if "menuprincipal" in url:
                score += 25
            if "contribuyente" in url or "buscar" in url or "tramite" in url:
                score += 35
            texto = self._page_text(page)
            if len(texto.strip()) < 30:
                score -= 25
            if "contribuyente" in texto:
                score += 40
            if "número documento" in texto or "numero documento" in texto:
                score += 55
            if "buscar contribuyente" in texto:
                score += 50
            if "registro contribuyente natural" in texto:
                score += 60
            if "modificación contribuyente" in texto or "modificacion contribuyente" in texto:
                score += 25
            return score
        except Exception:
            return -1

    def identificar_pantalla(self, page: Page | None = None) -> str:
        """
        Identifica el layout actual en la misma ventana RUAT.
        Orden: de lo más específico a lo más general.
        """
        page = page or self._page_activa()
        try:
            page.wait_for_timeout(200)
        except Exception:
            pass
        url = (page.url or "").lower()
        texto = self._page_text(page)

        def tiene(*frags: str) -> bool:
            return all(f.lower() in texto for f in frags)

        def tiene_alguno(*frags: str) -> bool:
            return any(f.lower() in texto for f in frags)

        # --- Alta / tramitación (más adelante en el flujo) ---
        if tiene_alguno("imprimir reporte", "reporte de control") and tiene_alguno("grabar", "salir"):
            return "confirmar"
        if tiene_alguno("editar fotografía", "editar fotografia") or (
            tiene("procesar") and tiene("finalizar") and ("fotografía" in texto or "fotografia" in texto)
        ):
            return "editar_foto"
        if tiene_alguno("registrar imágenes", "registrar imagenes") or (
            "fotografía" in texto and "anverso" in texto
        ):
            return "imagenes"
        if tiene_alguno("información adicional", "informacion adicional") and "celular" in texto:
            return "info_adicional"
        if "apoderado" in texto and tiene_alguno("desea registrar", "¿desea"):
            return "apoderado"
        if tiene_alguno("domicilio legal", "búsqueda avanzada de domicilio", "busqueda avanzada de domicilio"):
            return "domicilio"
        if tiene_alguno("datos generales", "estado civil") and tiene_alguno("fecha de nacimiento", "género", "genero"):
            return "datos_generales"
        if tiene_alguno("recepcionar documentación", "recepcionar documentacion", "documento de identidad"):
            if "grabar" in texto or "documentación" in texto or "documentacion" in texto:
                return "recepcionar"

        # --- Buscar / resultados ---
        if self._ya_en_buscar_contribuyente(page):
            if tiene("resultados") and (
                self._hay_coincidencia(page)
                or tiene_alguno("gobierno municipal", "nuevo contribuyente", "pmc")
            ):
                return "resultados_busqueda"
            return "buscar"

        # --- Menú / submenú (detección flexible por texto y controles) ---
        if self._link_registro_visible(page) or (
            "registro contribuyente natural" in texto
            and tiene_alguno("baja", "modificación", "modificacion", "contribuyente natural")
        ):
            return "submenu_contribuyente_natural"

        if self._hay_contribuyente_natural_menu(page):
            return "menu_principal"

        if "menuprincipalcontroller" in url or (
            "menuprincipal" in url and "armadosubmenu" not in url and "submenu" not in url
        ):
            return "menu_principal"

        if "armadosubmenu" in url or "submenu" in url:
            return "submenu_otro"

        if "login" in url or tiene_alguno("iniciar sesión", "iniciar sesion", "usuario", "contraseña", "contrasena"):
            if "ruat" in url or "municipios" in url:
                return "login_ruat"

        if "ruat" in url or "municipios" in url or "contribuyentes" in url:
            return "ruat_otra"

        return "desconocida"

    def _hay_contribuyente_natural_menu(self, page: Page) -> bool:
        """Link del menú principal (no el de Registro…)."""
        if self._link_registro_visible(page):
            return False
        patrones = [
            r"^Contribuyente\s+Natural$",
            r"Contribuyente\s+Natural",
        ]
        for pat in patrones:
            if self._hay_control_nombre(page, pat):
                return True
        texto = self._page_text(page)
        # En menú suele aparecer la columna REGISTRO CONTRIBUYENTES + el ítem
        if "contribuyente natural" in texto and "registro contribuyente natural" not in texto:
            return True
        return False

    def _hay_control_nombre(self, page: Page, name_pattern: str) -> bool:
        pat = re.compile(str(name_pattern), re.I)
        for scope in self._scopes(page):
            for role in ("link", "button", "menuitem"):
                try:
                    if scope.get_by_role(role, name=pat).count():
                        return True
                except Exception:
                    continue
            try:
                if scope.locator("a").filter(has_text=pat).count():
                    return True
            except Exception:
                pass
            try:
                # RUAT a veces pone el texto en td/span clickeable
                locs = scope.locator("a, td, span, div, li").filter(has_text=pat)
                n = min(locs.count(), 12)
                for i in range(n):
                    try:
                        txt = (locs.nth(i).inner_text(timeout=400) or "").strip()
                        if len(txt) <= 60 and pat.search(txt):
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
        return False

    def _forzar_menu_principal(self) -> Page:
        """
        Vuelve al menú principal SIN abrir URL.
        Intenta clic en «Menú Principal»; si ya está el menú, no hace nada.
        Si no puede, pide al operador que deje el menú visible.
        """
        page = self._page_activa()
        if self.menu_principal_listo():
            log.info("Ya en menú principal — no navego")
            return page

        log.info("Intentando clic «Menú Principal» (sin goto URL)…")
        if self._click_por_nombre(page, r"Men[uú]\s+Principal"):
            page.wait_for_timeout(800)
            page = self._page_activa()
            if self.menu_principal_listo() or self._hay_contribuyente_natural_menu(page):
                return page

        # A veces el link está solo en sidebar del submenú
        if self._click_por_nombre(page, r"^Men[uú]\s+Principal$"):
            page.wait_for_timeout(800)
            page = self._page_activa()
            if self.menu_principal_listo() or self._hay_contribuyente_natural_menu(page):
                return page

        raise RuntimeError(
            "No pude volver al menú principal sin abrir URL. "
            "En Firefox del agente: pulse «Menú Principal», deje visible Contribuyente Natural "
            "y use Reintentar envío / Iniciar."
        )

    def _asegurar_pantalla_buscar(self, page: Page) -> Page:
        """
        Desde cualquier pantalla, llega a Buscar Contribuyente:
        menú → Contribuyente Natural → Registro Contribuyente Natural → Buscar.
        """
        for intento in range(8):
            page = self._page_activa()
            pantalla = self.identificar_pantalla(page)
            snippet = (self._page_text(page) or "")[:120].replace("\n", " ")
            log.info(
                "Pantalla=%s intento=%s url=%s texto=%r",
                pantalla,
                intento + 1,
                (page.url or "")[:100],
                snippet,
            )

            if pantalla in ("buscar", "resultados_busqueda"):
                return page

            if pantalla == "login_ruat":
                raise RuntimeError(
                    "RUAT pide inicio de sesión. Inicie sesión en la ventana del agente y vuelva a enviar."
                )

            if pantalla == "submenu_contribuyente_natural":
                try:
                    page = self._ir_registro_contribuyente_natural(page)
                except Exception as exc:
                    log.warning("Registro falló (%s) — vuelvo al menú", exc)
                    page = self._forzar_menu_principal()
                continue

            if pantalla == "menu_principal":
                try:
                    page = self._ir_contribuyente_natural(page)
                    if not self._ya_en_buscar_contribuyente(page):
                        page = self._ir_registro_contribuyente_natural(page)
                except Exception as exc:
                    log.warning("Navegación desde menú falló (%s)", exc)
                    page = self._forzar_menu_principal()
                continue

            # desconocida / otra pantalla / submenú ajeno → menú y reintentar
            log.info("Reinicio desde menú (estaba en %s)", pantalla)
            page = self._forzar_menu_principal()
            # Tras el goto, intentar el flujo completo aunque la detección falle
            try:
                if self._hay_contribuyente_natural_menu(page) or self.identificar_pantalla(page) == "menu_principal":
                    page = self._ir_contribuyente_natural(page)
                elif self._click_por_nombre(page, r"Contribuyente\s+Natural"):
                    page = self._esperar_ui(
                        lambda p: self._link_registro_visible(p) or self._ya_en_buscar_contribuyente(p),
                        timeout_ms=15000,
                        desc="Contribuyente Natural",
                    )
                if self._ya_en_buscar_contribuyente(page):
                    return page
                if self._link_registro_visible(page) or "registro contribuyente natural" in self._page_text(page):
                    page = self._ir_registro_contribuyente_natural(page)
            except Exception as exc:
                log.warning("Intento de flujo tras menú: %s", exc)

        page = self._page_activa()
        if self._ya_en_buscar_contribuyente(page):
            return page
        pant = self.identificar_pantalla(page)
        raise RuntimeError(
            f"No llegué a Buscar Contribuyente (pantalla={pant}, url={(page.url or '')[:80]}). "
            "Abra el menú principal de RUAT en la ventana del agente, inicie sesión si hace falta y vuelva a enviar."
        )

    def _pick_page(self, context: BrowserContext) -> Page:
        """Elige la pestaña RUAT del contexto (normalmente hay una sola)."""
        pages = [p for p in context.pages if not p.is_closed()]
        if not pages:
            return context.new_page()
        if self.page and not self.page.is_closed() and self.page in pages:
            if self._page_score(self.page) >= 15:
                return self.page
        scored = sorted(
            ((self._page_score(p), i, p) for i, p in enumerate(pages)),
            key=lambda t: (t[0], t[1]),
            reverse=True,
        )
        best = scored[0][2]
        try:
            best.bring_to_front()
        except Exception:
            pass
        return best

    def close(self) -> None:
        try:
            if self.mode == "persistent" and self._context:
                self._context.close()
            elif self._browser:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self.page = None
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None

    def _pagina_viva(self) -> bool:
        try:
            if not self.page:
                return False
            if self.page.is_closed():
                return False
            _ = self.page.url
            return True
        except Exception:
            return False

    def _page_activa(self) -> Page:
        """Misma ventana Nightly: reutilizar self.page; solo recuperar si murió."""
        if self._pagina_viva():
            assert self.page is not None
            return self.page
        if self._context:
            try:
                self.page = self._pick_page(self._context)
                if self.page and not self.page.is_closed():
                    return self.page
            except Exception:
                pass
        self.ensure_connected()
        assert self.page is not None
        return self.page

    def ensure_connected(self) -> None:
        """Reabre Nightly solo si se cerró; no busca otras ventanas."""
        if self.dry_run:
            return
        if self._pagina_viva() and self._context is not None:
            return
        if self._context is not None:
            try:
                self.page = self._pick_page(self._context)
                if self.page and not self.page.is_closed():
                    log.info("Recuperé la pestaña Nightly · url=%s", self.page.url)
                    self.page.on("dialog", self._on_browser_dialog)
                    # No goto automático: el operador mantiene la sesión RUAT
                    return
            except Exception as exc:
                log.warning("No pude recuperar pestaña (%s) — reinicio Nightly", exc)
        log.warning("Firefox/Nightly no responde — reconectando…")
        try:
            self.close()
        except Exception:
            pass
        self.connect()

    def _esperar_ui(self, predicado, timeout_ms: int = 12000, desc: str = "UI") -> Page:
        """Espera a que cambie el diseño en la MISMA ventana (sin popups)."""
        page = self._page_activa()
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            page = self._page_activa()
            try:
                if predicado(page):
                    log.info("UI lista: %s · %s", desc, (page.url or "")[:100])
                    return page
            except Exception:
                pass
            page.wait_for_timeout(250)
        return self._page_activa()

    def _ir_menu_principal(self) -> Page:
        page = self._page_activa()
        url = (page.url or "").lower()
        if self._ya_en_buscar_contribuyente(page) or self._link_registro_visible(page):
            return page
        if self._hay_contribuyente_natural_menu(page):
            return page
        if "menuprincipalcontroller" in url or (
            "menuprincipal" in url and "armadosubmenu" not in url and "submenu" not in url
        ):
            return page
        return self._forzar_menu_principal()

    def _patrones_registro(self) -> list[str]:
        patterns = self._sel("registro_contribuyente_natural", "link_names", default=None)
        if isinstance(patterns, list) and patterns:
            return [str(p) for p in patterns]
        primary = self._sel(
            "registro_contribuyente_natural",
            "link_name",
            default=r"^Registro\s+(de\s+)?Contribuyente\s+Natural$",
        )
        return [
            str(primary),
            r"^Registro\s+Contribuyente\s+Natural$",
            r"^Registro\s+de\s+Contribuyente\s+Natural$",
            r"Registro\s+Contribuyente\s+Natural",
        ]

    def _link_registro_visible(self, page: Page) -> bool:
        """True solo si en el submenú aparece el enlace Registro (Contribuyente Natural)."""
        for pat in self._patrones_registro():
            rx = re.compile(str(pat), re.I)
            for scope in self._scopes(page):
                try:
                    if scope.get_by_role("link", name=rx).count():
                        return True
                except Exception:
                    pass
                try:
                    if scope.locator("a").filter(has_text=rx).count():
                        return True
                except Exception:
                    pass
        texto = self._page_text(page)
        return "registro contribuyente natural" in texto and (
            "baja de contribuyente" in texto
            or "modificación contribuyente" in texto
            or "modificacion contribuyente" in texto
            or "contribuyente natural" in texto
        )

    def _ya_en_submenu_contribuyente_natural(self, page: Page) -> bool:
        """Submenú CONTRIBUYENTE NATURAL (no cualquier armadoSubmenu)."""
        return self._link_registro_visible(page)

    def _ya_en_buscar_contribuyente(self, page: Page) -> bool:
        """Formulario Buscar (layout tras clic en Registro…), no el link del submenú."""
        try:
            for scope in self._scopes(page):
                try:
                    if scope.get_by_text(re.compile(r"BUSCAR\s+CONTRIBUYENTE", re.I)).count():
                        return True
                    if scope.get_by_label(re.compile(r"N[uú]mero\s+Documento", re.I)).count():
                        return True
                except Exception:
                    continue
            texto = self._page_text(page)
            if "buscar contribuyente" in texto and (
                "número documento" in texto or "numero documento" in texto or "criterios" in texto
            ):
                return True
        except Exception:
            return False
        return False

    def _scopes(self, page: Page):
        yield page
        try:
            for fr in page.frames:
                yield fr
        except Exception:
            return

    def _click_por_nombre(self, page: Page, name_pattern: str) -> bool:
        """Clic en la misma ventana (página + iframes)."""
        pat = re.compile(str(name_pattern), re.I)
        for scope in self._scopes(page):
            for role in ("link", "button", "menuitem"):
                try:
                    loc = scope.get_by_role(role, name=pat)
                    if loc.count():
                        loc.first.click(timeout=12000, force=True)
                        return True
                except Exception:
                    continue
            try:
                loc = scope.locator("a").filter(has_text=pat)
                if loc.count():
                    loc.first.click(timeout=12000, force=True)
                    return True
            except Exception:
                pass
            try:
                loc = scope.locator("td, span, div, li").filter(has_text=pat)
                n = min(loc.count(), 8)
                for i in range(n):
                    try:
                        el = loc.nth(i)
                        txt = (el.inner_text(timeout=500) or "").strip()
                        if len(txt) > 80:
                            continue
                        if pat.search(txt):
                            el.click(timeout=12000, force=True)
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
        return False

    def _click_menu(self, name_pattern: str, esperar=None, timeout_ms: int = 12000) -> Page:
        """Clic y espera el nuevo layout en la misma ventana."""
        last_err: Exception | None = None
        for attempt in range(3):
            page = self._page_activa()
            try:
                if not self._click_por_nombre(page, name_pattern):
                    log.warning("No se encontró «%s» en la ventana actual", name_pattern)
                    return page
                page.wait_for_timeout(500)
                if esperar:
                    return self._esperar_ui(esperar, timeout_ms=timeout_ms, desc=name_pattern)
                page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(400)
                return self._page_activa()
            except Exception as exc:
                last_err = exc
                msg = str(exc).lower()
                if "closed" in msg or "target page" in msg:
                    log.warning("Página cerrada al clic «%s» (intento %s)", name_pattern, attempt + 1)
                    self.ensure_connected()
                    continue
                raise
        if last_err:
            raise last_err
        return self._page_activa()

    def _ir_contribuyente_natural(self, page: Page) -> Page:
        """Paso 1: menú → Contribuyente Natural (esperar submenú con enlace Registro)."""
        page = self._page_activa()
        if self._ya_en_buscar_contribuyente(page):
            log.info("Ya en Buscar Contribuyente — no reabro menú")
            return page
        if self._link_registro_visible(page):
            log.info("Ya en submenú Contribuyente Natural (Registro visible)")
            return page

        nombre = self._sel("contribuyente_natural", "link_name", default=r"Contribuyente\s+Natural")
        candidatos_cn = [
            str(nombre),
            r"^Contribuyente\s+Natural$",
            r"Contribuyente\s+Natural",
        ]
        log.info("Paso 1/2: abrir Contribuyente Natural…")
        page_ok = False
        for pat in candidatos_cn:
            page = self._click_menu(
                pat,
                esperar=lambda p: self._link_registro_visible(p) or self._ya_en_buscar_contribuyente(p),
                timeout_ms=15000,
            )
            if self._ya_en_buscar_contribuyente(page) or self._link_registro_visible(page):
                page_ok = True
                break
        if page_ok:
            return page

        # Reintento desde menú principal
        log.warning("Submenú no apareció — reintento desde menú principal")
        page = self._forzar_menu_principal()
        for pat in candidatos_cn:
            page = self._click_menu(
                pat,
                esperar=lambda p: self._link_registro_visible(p) or self._ya_en_buscar_contribuyente(p),
                timeout_ms=15000,
            )
            if self._ya_en_buscar_contribuyente(page) or self._link_registro_visible(page):
                return page
        raise RuntimeError(
            "No pude abrir el submenú «Contribuyente Natural». "
            "Inicie sesión en RUAT en la ventana del agente, deje el menú principal visible y vuelva a enviar."
        )

    def _ir_registro_contribuyente_natural(self, page: Page) -> Page:
        """Paso 2: submenú → Registro Contribuyente Natural → Buscar."""
        page = self._page_activa()
        if self._ya_en_buscar_contribuyente(page):
            log.info("Ya en Buscar Contribuyente — sigo con CI")
            return page

        # Siempre asegurar paso 1 antes del Registro
        page = self._ir_contribuyente_natural(page)
        if self._ya_en_buscar_contribuyente(page):
            return page

        log.info("Paso 2/2: abrir Registro Contribuyente Natural…")
        for pat in self._patrones_registro():
            page = self._page_activa()
            if self._ya_en_buscar_contribuyente(page):
                return page
            if not self._link_registro_visible(page):
                page = self._ir_contribuyente_natural(page)
                if self._ya_en_buscar_contribuyente(page):
                    return page
            if not self._click_por_nombre(page, pat):
                continue
            log.info("Clic «%s» — espero formulario Buscar", pat)
            page = self._esperar_ui(self._ya_en_buscar_contribuyente, timeout_ms=15000, desc="Buscar Contribuyente")
            if self._ya_en_buscar_contribuyente(page):
                return page

        page = self._page_activa()
        if self._ya_en_buscar_contribuyente(page):
            return page
        raise RuntimeError(
            "No pude abrir «Registro Contribuyente Natural». "
            "Debe verse el submenú CONTRIBUYENTE NATURAL y luego el enlace Registro. Vuelva a enviar."
        )

    def procesar(self, doc: dict) -> None:
        """
        Máquina de estados: identificar pantalla → acción del paso → verificar destino.
        Modo seguro: llega hasta Imprimir Reporte; no pulsa Grabar final.
        """
        self.ensure_connected()
        self._paso_actual = "inicio"
        page = self._page_activa()

        if self.dry_run:
            log.info(
                "[DRY_RUN] CI=%s nombres=%s foto=%s",
                doc.get("numero_documento"),
                doc.get("nombres"),
                bool(doc.get("foto_url")),
            )
            return

        # Identificar ventana y seguir el flujo hasta Buscar (sin abrir URL)
        if not self.menu_principal_listo() and self.identificar_pantalla(page) not in (
            "submenu_contribuyente_natural",
            "buscar",
            "resultados_busqueda",
            "recepcionar",
            "datos_generales",
            "domicilio",
        ):
            # Permitir continuar si ya está a mitad de un flujo útil; si no, exigir menú
            pant0 = self.identificar_pantalla(page)
            if pant0 in ("desconocida", "login_ruat", "ruat_otra", "submenu_otro"):
                raise RuntimeError(self.motivo_menu_no_listo())

        def fase_llegar_y_buscar() -> None:
            p = self._asegurar_pantalla_buscar(self._page_activa())
            self._buscar_contribuyente(p, doc)

        self._ejecutar_paso(
            "buscar",
            fase_llegar_y_buscar,
            destinos=("resultados_busqueda", "buscar", "recepcionar"),
            max_intentos=3,
            recuperar_menu=True,
        )

        page = self._page_activa()
        rama = self._clasificar_resultado_busqueda(page)
        if rama == "ya_en_municipio":
            nombre = self._nombre_en_resultado(page) or (
                f"{doc.get('nombres') or ''} {doc.get('apellidos') or ''}".strip()
            )
            ci = doc.get("numero_documento") or ""
            detalle = f"CI {ci}" + (f", {nombre}" if nombre else "")
            raise ContribuyenteYaRegistrado(
                f"El contribuyente ya tiene un registro en Riberalta ({detalle}). "
                "No se inició un nuevo alta. Use Modificación si corresponde."
            )

        self._validar_datos_ocr(doc)
        if rama == "asociar":
            log.info("Otros municipios en Resultados → Nuevo Contribuyente (sin Asociar)")
        else:
            log.info("Sin registro usable → Nuevo Contribuyente")

        def fase_nuevo() -> None:
            self._click_nuevo_contribuyente(self._page_activa())

        # Tras Nuevo puede ir directo a recepcionar
        if self.identificar_pantalla(page) != "recepcionar":
            self._ejecutar_paso(
                "nuevo_contribuyente",
                fase_nuevo,
                destinos=("recepcionar", "datos_generales"),
                max_intentos=2,
                recuperar_menu=False,
            )

        self._ejecutar_paso(
            "recepcionar",
            lambda: self._recepcionar_documentacion(self._page_activa()),
            destinos=("datos_generales",),
            max_intentos=3,
        )

        self._ejecutar_paso(
            "datos_generales",
            lambda: self._datos_generales(self._page_activa(), doc),
            destinos=("domicilio", "apoderado"),
            max_intentos=3,
        )

        self._ejecutar_paso(
            "domicilio",
            lambda: self._domicilio_legal(self._page_activa(), doc),
            destinos=("apoderado", "info_adicional", "imagenes"),
            max_intentos=3,
        )

        # Apoderado puede ser nativo (ya dismiss) o HTML
        self._paso_actual = "apoderado"
        try:
            self._cancelar_apoderado(self._page_activa())
        except Exception as exc:
            log.warning("Apoderado (no bloqueante): %s", exc)

        self._ejecutar_paso(
            "info_adicional",
            lambda: self._info_adicional(self._page_activa(), doc),
            destinos=("imagenes", "editar_foto", "confirmar"),
            max_intentos=3,
        )

        self._ejecutar_paso(
            "imagenes",
            lambda: self._subir_fotografia(self._page_activa(), doc),
            destinos=("confirmar", "editar_foto"),
            max_intentos=3,
        )

        # Tras foto a veces queda en editar_foto hasta Finalizar; subir_fotografia ya lo maneja
        if self.identificar_pantalla(self._page_activa()) == "editar_foto":
            self._ejecutar_paso(
                "editar_foto",
                lambda: self._editar_fotografia_procesar(self._page_activa()),
                destinos=("imagenes", "confirmar"),
                max_intentos=2,
            )

        self._ejecutar_paso(
            "confirmar",
            lambda: self._confirmar_tramite_imprimir(self._page_activa()),
            destinos=("confirmar",),
            max_intentos=2,
        )
        self._paso_actual = "completado"
        log.info("Flujo RUAT completado (modo seguro — NO se pulsó Grabar)")

    # --- pasos ---

    def _sel(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.selectors
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def _input_texto_visible(self, scope, css: str, idx: int = 0):
        """Primer(os) input(s) de texto visibles en página o iframe."""
        loc = scope.locator(css)
        visibles = []
        try:
            n = min(loc.count(), 12)
        except Exception:
            return None
        for i in range(n):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    visibles.append(el)
            except Exception:
                continue
        if idx < len(visibles):
            return visibles[idx]
        return visibles[0] if visibles else None

    def _escribir_en_input(self, campo, valor: str, page: Page) -> bool:
        """Rellena un input RUAT (fill suele fallar en JSP antiguos). Verifica el valor."""
        strategies = []

        def via_fill() -> None:
            campo.click(timeout=3000, force=True)
            campo.fill("", force=True, timeout=3000)
            campo.fill(valor, force=True, timeout=5000)

        def via_type() -> None:
            campo.click(timeout=3000, force=True)
            try:
                campo.press("Control+a", timeout=2000)
            except Exception:
                pass
            try:
                campo.press("Backspace", timeout=2000)
            except Exception:
                pass
            # press_sequentially dispara keydown/keypress/keyup (RUAT lo necesita)
            campo.press_sequentially(valor, delay=40, timeout=15000)

        def via_js() -> None:
            campo.evaluate(
                """(el, v) => {
                    el.focus();
                    el.select && el.select();
                    el.value = '';
                    el.value = v;
                    for (const ev of ['input', 'change', 'blur', 'keyup']) {
                      el.dispatchEvent(new Event(ev, { bubbles: true }));
                    }
                }""",
                valor,
            )

        strategies.extend([("fill", via_fill), ("type", via_type), ("js", via_js)])

        for name, fn in strategies:
            try:
                fn()
                time.sleep(0.15)
                try:
                    actual = (campo.input_value(timeout=2000) or "").strip()
                except Exception:
                    actual = ""
                if actual == valor or actual.replace(" ", "") == valor:
                    log.info("CI escrito con estrategia «%s» → %r", name, actual)
                    return True
                log.warning("Estrategia «%s»: valor quedó %r (esperado %r)", name, actual, valor)
            except Exception as exc:
                log.warning("Estrategia «%s» falló: %s", name, exc)

        # Último recurso: teclado a nivel página (el campo ya debería tener foco)
        try:
            campo.click(timeout=3000, force=True)
            page.keyboard.type(valor, delay=50)
            time.sleep(0.2)
            actual = (campo.input_value(timeout=2000) or "").strip()
            if actual == valor or valor in actual:
                log.info("CI escrito con keyboard.type → %r", actual)
                return True
        except Exception as exc:
            log.warning("keyboard.type falló: %s", exc)
        return False

    def _rellenar_ci_en_frames(self, page: Page, numero: str) -> bool:
        """Busca el input Número Documento en cada frame y lo setea por JS (más fiable en RUAT)."""
        js = """
        (numero) => {
          const okType = (t) => {
            t = (t || 'text').toLowerCase();
            return t === 'text' || t === '' || t === 'search' || t === 'tel' || t === 'number';
          };
          const visible = (el) => !!(el && el.offsetParent !== null && el.disabled !== true);
          const body = (document.body && document.body.innerText || '').toLowerCase();
          const enForm =
            body.includes('buscar contribuyente') ||
            body.includes('criterios') ||
            body.includes('número documento') ||
            body.includes('numero documento');
          if (!enForm) return { ok: false, reason: 'no-form' };

          const inputs = Array.from(document.querySelectorAll('input')).filter(
            (inp) => okType(inp.type) && visible(inp)
          );
          let target = null;
          for (const inp of inputs) {
            const row = inp.closest('tr') || inp.parentElement;
            const txt = ((row && row.innerText) || '').toLowerCase();
            if (txt.includes('numero documento') || txt.includes('número documento')) {
              const rowIns = Array.from(row.querySelectorAll('input')).filter(
                (i) => okType(i.type) && visible(i)
              );
              // Caja grande del CI = primera de la fila (la chica es complemento)
              target = rowIns[0] || inp;
              break;
            }
          }
          if (!target) {
            // Sección criterios: primer input de texto
            const criterios = Array.from(document.querySelectorAll('table, fieldset, div')).find((n) =>
              /criterios\\s*b[uú]squeda/i.test(n.innerText || '')
            );
            if (criterios) {
              const ins = Array.from(criterios.querySelectorAll('input')).filter(
                (i) => okType(i.type) && visible(i)
              );
              target = ins[0] || null;
            }
          }
          if (!target && inputs.length) target = inputs[0];
          if (!target) return { ok: false, reason: 'no-input', n: inputs.length };

          target.focus();
          target.value = numero;
          for (const ev of ['focus', 'input', 'keydown', 'keyup', 'change']) {
            try { target.dispatchEvent(new Event(ev, { bubbles: true })); } catch (e) {}
          }
          return {
            ok: true,
            value: target.value,
            name: target.name || '',
            id: target.id || '',
          };
        }
        """
        for scope in self._scopes(page):
            try:
                # Frame/Page.evaluate
                res = scope.evaluate(js, numero)
            except Exception as exc:
                log.debug("evaluate CI en scope: %s", exc)
                continue
            if not isinstance(res, dict):
                continue
            if res.get("ok") and str(res.get("value") or "").strip() == numero:
                log.info(
                    "CI por JS en frame · name=%s id=%s",
                    res.get("name"),
                    res.get("id"),
                )
                return True
            if res.get("ok"):
                log.warning("JS setéó pero value=%r", res.get("value"))
        return False

    def _localizar_campo_numero_documento(self, page: Page):
        """
        Localiza la caja grande de Número Documento (no el complemento).
        Prioriza la fila del label dentro de Criterios / BUSCAR CONTRIBUYENTE.
        """
        label_rx = re.compile(r"N[uú]mero\s+Documento", re.I)
        css = (
            "input[type='text'], input:not([type]), input[type=''], "
            "input[type='search'], input[type='tel'], input[type='number']"
        )
        css = str(self._sel("buscar", "input_documento", default=css))

        candidatos: list = []

        for scope in self._scopes(page):
            # A) Fila que contiene el label → primer input de esa fila
            try:
                filas = scope.locator("tr").filter(has_text=label_rx)
                n = min(filas.count(), 4)
                for i in range(n):
                    fila = filas.nth(i)
                    ins = fila.locator(css)
                    if ins.count() >= 1 and ins.first.is_visible():
                        candidatos.append(ins.first)
                        break
            except Exception:
                pass

            # B) Bloque Criterios Búsqueda
            try:
                bloque = scope.locator("table, fieldset, div").filter(
                    has_text=re.compile(r"Criterios\s+B[uú]squeda", re.I)
                )
                if bloque.count():
                    el = self._input_texto_visible(bloque.first, css, 0)
                    if el is not None:
                        candidatos.append(el)
            except Exception:
                pass

            # C) Scope con título BUSCAR CONTRIBUYENTE
            try:
                if scope.get_by_text(re.compile(r"BUSCAR\s+CONTRIBUYENTE", re.I)).count():
                    el = self._input_texto_visible(scope, css, 0)
                    if el is not None:
                        candidatos.append(el)
            except Exception:
                pass

            # D) name/id típicos Struts/JSP
            for sel in (
                "input[name*='documento' i]",
                "input[name*='Documento' i]",
                "input[id*='documento' i]",
                "input[name*='nroDoc' i]",
                "input[name*='numDoc' i]",
            ):
                try:
                    loc = scope.locator(sel)
                    if loc.count() and loc.first.is_visible():
                        candidatos.append(loc.first)
                except Exception:
                    continue

        # Log de ayuda
        try:
            log.info("Candidatos Número Documento: %s", len(candidatos))
        except Exception:
            pass

        return candidatos[0] if candidatos else None

    def _buscar_contribuyente(self, page: Page, doc: dict) -> None:
        page = self._esperar_ui(self._ya_en_buscar_contribuyente, timeout_ms=12000, desc="formulario Buscar")
        page = self._page_activa()
        numero = (doc.get("numero_documento") or "").split("-")[0].strip()
        numero = re.sub(r"\D", "", numero) or numero
        if not numero:
            raise RuntimeError("numero_documento vacío")

        log.info("Rellenando Número Documento = %s", numero)

        # 1) JS directo en frames (más fiable en RUAT/JSP)
        escrito = self._rellenar_ci_en_frames(page, numero)

        # 2) Locator Playwright + fill/type/js
        if not escrito:
            campo = self._localizar_campo_numero_documento(page)
            if campo is None:
                raise RuntimeError(
                    "No encontré el campo Número Documento en Buscar Contribuyente. "
                    "Deje abierta esa pantalla (con el cuadro Criterios Búsqueda) y vuelva a enviar."
                )
            escrito = self._escribir_en_input(campo, numero, page)

        if not escrito:
            raise RuntimeError(
                f"El campo Número Documento no aceptó el CI ({numero}). "
                "Haga clic en el campo, reinicie el agente (v1.3.9+) y vuelva a enviar."
            )

        # Tipo Documento = CEDULA DE IDENTIDAD (suele venir ya seleccionado)
        tipo_label = self._sel("buscar", "tipo_documento_label", default="CEDULA DE IDENTIDAD")
        label_tipo = self._sel("buscar", "label_tipo_documento", default="Tipo Documento")
        tipo_ok = False
        for scope in self._scopes(page):
            tipo = scope.get_by_label(re.compile(str(label_tipo), re.I))
            if tipo.count() == 0:
                tipo = scope.locator("select").filter(has_text=re.compile(r"CEDULA|IDENTIDAD", re.I))
            if tipo.count():
                try:
                    tipo.first.select_option(label=re.compile(str(tipo_label), re.I), timeout=5000)
                except Exception:
                    pass
                tipo_ok = True
                break
        if not tipo_ok:
            log.warning("No se pudo fijar tipo documento %s (puede ya estar seleccionado)", tipo_label)

        # Departamento Expedido → opción en blanco (regla fija Riberalta/RUAT)
        label_depto = self._sel("buscar", "label_departamento", default="Departamento Expedido")
        depto_ok = False
        for scope in self._scopes(page):
            depto = scope.get_by_label(re.compile(str(label_depto), re.I))
            if depto.count() == 0:
                sels = scope.locator("select")
                try:
                    nsel = sels.count()
                except Exception:
                    nsel = 0
                if nsel >= 2:
                    depto = sels.nth(1)
                elif nsel == 1:
                    depto = sels.first
                else:
                    continue
            try:
                target = depto.first if hasattr(depto, "first") and depto.count() else depto
                target.select_option(index=0, timeout=5000)
                log.info("Departamento Expedido dejado en blanco (índice 0)")
                depto_ok = True
                break
            except Exception:
                continue
        if not depto_ok:
            log.warning("No se pudo forzar Departamento Expedido en blanco")

        btn = self._sel("buscar", "boton_buscar", default="^Buscar$")
        clicked = False
        # Evitar «Búsqueda Avanzada»: solo botón exacto Buscar
        for scope in self._scopes(page):
            try:
                b = scope.get_by_role("button", name=re.compile(r"^Buscar$", re.I))
                if b.count():
                    b.first.click(timeout=8000, force=True)
                    clicked = True
                    break
            except Exception:
                continue
            try:
                b = scope.locator("input[type='submit'], input[type='button'], button").filter(
                    has_text=re.compile(r"^Buscar$", re.I)
                )
                if b.count():
                    b.first.click(timeout=8000, force=True)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            clicked = self._click_por_nombre(page, str(btn))
        if not clicked:
            raise RuntimeError("No encontré el botón Buscar en el formulario.")
        log.info("Clic en Buscar OK")
        page.wait_for_timeout(1200)

    def _validar_datos_ocr(self, doc: dict) -> None:
        """Género, estado civil y fecha: si faltan o son raros → avisar al operador."""
        problemas: list[str] = []

        genero = (doc.get("genero") or "").strip()
        if not genero:
            problemas.append("género vacío")
        elif not re.search(r"MASCULINO|FEMENINO|MASC|FEM|HOMBRE|MUJER|\bM\b|\bF\b", genero, re.I):
            problemas.append(f"género raro («{genero}»)")

        ec = (doc.get("estado_civil") or "").strip().upper()
        if not ec:
            problemas.append("estado civil vacío")
        else:
            ec_ok = re.search(
                r"SOLTERO|CASADO|DIVORCIADO|VIUDO|UNION|CONVIV|SEPARADO",
                ec,
                re.I,
            )
            if not ec_ok:
                problemas.append(f"estado civil raro («{doc.get('estado_civil')}»)")

        fecha_raw = (doc.get("fecha_nacimiento") or "").strip()
        fecha = self._normalizar_fecha_dd_mm_aaaa(fecha_raw)
        if not fecha_raw:
            problemas.append("fecha de nacimiento vacía")
        elif not re.match(r"^\d{2}/\d{2}/\d{4}$", fecha):
            problemas.append(f"fecha de nacimiento rara («{fecha_raw}»)")
        else:
            d, m, y = (int(x) for x in fecha.split("/"))
            if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100):
                problemas.append(f"fecha de nacimiento inválida («{fecha}»)")

        if problemas:
            raise DatosOcrInvalidos(
                "Datos del CI incompletos o raros: "
                + "; ".join(problemas)
                + ". Corrija en Verificar y vuelva a enviar al PC."
            )

    def _clasificar_resultado_busqueda(self, page: Page) -> str:
        """
        Tras Buscar:
        - ya_en_municipio: Resultados con Gobierno Municipal = RIBERALTA
        - asociar: había link Asociar (otro municipio) — ahora se trata como alta nueva
        - nuevo: sin fila local / Nuevo Contribuyente
        """
        mun = str(self._sel("buscar", "municipio_local", default="RIBERALTA"))
        page.wait_for_timeout(400)

        # ¿Hay tabla de resultados con el municipio local?
        if page.get_by_text(re.compile(r"Resultados", re.I)).count():
            rows = page.locator("table tr")
            for i in range(min(rows.count(), 30)):
                txt = (rows.nth(i).inner_text() or "").strip()
                if not txt:
                    continue
                upper = txt.upper()
                if mun.upper() in upper and (
                    re.search(r"\bCI\b", upper) or re.search(r"\d{5,}", txt)
                ):
                    # Evitar fila de encabezado
                    if "NOMBRE COMPLETO" in upper and "PMC" in upper:
                        continue
                    log.info("Resultado local detectado: %s", txt.replace("\n", " ")[:120])
                    return "ya_en_municipio"

        if self._hay_coincidencia(page):
            return "asociar"
        return "nuevo"

    def _nombre_en_resultado(self, page: Page) -> str:
        try:
            # Segunda/tercera celda típica: Nombre Completo
            rows = page.locator("table").locator("tr").filter(has_text=re.compile(r"CI\s*\d+", re.I))
            if rows.count():
                cells = rows.first.locator("td")
                if cells.count() >= 3:
                    return (cells.nth(2).inner_text() or "").strip()
        except Exception:
            pass
        return ""

    def _click_nuevo_contribuyente(self, page: Page) -> None:
        name = self._sel("buscar", "boton_nuevo", default="^Nuevo Contribuyente$")
        btn = page.get_by_role("button", name=re.compile(str(name), re.I))
        if btn.count() == 0:
            btn = page.get_by_text(re.compile(r"Nuevo\s+Contribuyente", re.I))
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(900)
            log.info("Clic en Nuevo Contribuyente")
        else:
            log.warning("No se encontró Nuevo Contribuyente — se asume alta ya iniciada")

    def _hay_coincidencia(self, page: Page) -> bool:
        name = self._sel("asociar", "link_name", default="^Asociar$")
        return page.get_by_role("link", name=re.compile(str(name), re.I)).count() > 0

    def _click_asociar(self, page: Page) -> None:
        name = self._sel("asociar", "link_name", default="^Asociar$")
        page.get_by_role("link", name=re.compile(str(name), re.I)).first.click()
        page.wait_for_timeout(800)

    def _click_asociar_mejor_nombre(self, page: Page, doc: dict) -> None:
        """
        Otros municipios: Asociar la fila cuyo Nombre Completo más se parezca al OCR.
        No marcar checkbox Imagen/Fotografía.
        """
        mun_local = str(self._sel("buscar", "municipio_local", default="RIBERALTA")).upper()
        objetivo = self._norm_lugar(
            f"{doc.get('nombres') or ''} {doc.get('apellidos') or ''} "
            f"{doc.get('primer_apellido') or ''} {doc.get('segundo_apellido') or ''}"
        )
        asociar_re = str(self._sel("asociar", "link_name", default="^Asociar$"))

        # Asegurar que ningún checkbox de Imagen esté marcado en Resultados
        for cb in page.locator("table input[type='checkbox']").all():
            try:
                if cb.is_checked():
                    cb.uncheck(force=True)
            except Exception:
                pass

        rows = page.locator("table tr").filter(
            has=page.get_by_role("link", name=re.compile(asociar_re, re.I))
        )
        best_i = -1
        best_score = -1.0
        for i in range(min(rows.count(), 40)):
            row = rows.nth(i)
            txt = (row.inner_text() or "").strip()
            upper = txt.upper()
            if mun_local and mun_local in upper:
                continue  # no asociar filas del municipio local aquí
            score = self._score_nombre(objetivo, self._norm_lugar(txt))
            if score > best_score:
                best_score = score
                best_i = i

        if best_i < 0 or best_score < 0.15:
            # Fallback: primer Asociar de otro municipio
            for i in range(min(rows.count(), 40)):
                row = rows.nth(i)
                upper = (row.inner_text() or "").upper()
                if mun_local in upper:
                    continue
                link = row.get_by_role("link", name=re.compile(asociar_re, re.I))
                if link.count():
                    log.warning(
                        "Asociar sin buen match de nombre (score=%.2f) → primera fila foránea",
                        best_score,
                    )
                    link.first.click()
                    page.wait_for_timeout(900)
                    return
            raise RuntimeError("Hay resultados de otros municipios pero no se pudo Asociar")

        row = rows.nth(best_i)
        log.info(
            "Asociar fila score=%.2f · %s",
            best_score,
            (row.inner_text() or "").replace("\n", " ")[:140],
        )
        row.get_by_role("link", name=re.compile(asociar_re, re.I)).first.click()
        page.wait_for_timeout(900)

    @staticmethod
    def _score_nombre(objetivo: str, candidato: str) -> float:
        if not objetivo or not candidato:
            return 0.0
        tokens = [t for t in objetivo.split() if len(t) > 1]
        if not tokens:
            return 0.0
        hits = sum(1 for t in tokens if t in candidato)
        return hits / len(tokens)

    def _marcar_checkbox_por_texto(self, page: Page, texto: str, *, marcar: bool = True) -> bool:
        """Marca/desmarca checkbox junto a un texto (página + iframes). RUAT suele usar frames."""
        label_rx = re.compile(re.escape(texto), re.I)
        js = """
        ([texto, marcar]) => {
          const body = (document.body && document.body.innerText || '').toLowerCase();
          if (!body.includes(texto.toLowerCase())) return { ok: false, reason: 'no-text' };
          const inputs = Array.from(document.querySelectorAll('input[type=checkbox]'));
          let target = null;
          for (const cb of inputs) {
            const row = cb.closest('tr') || cb.closest('label') || cb.parentElement;
            const txt = ((row && row.innerText) || '').toLowerCase();
            if (txt.includes(texto.toLowerCase())) {
              // Evitar coincidir solo por "documento" genérico si hay varios:
              // preferir fila que contenga el texto completo
              target = cb;
              if (txt.includes('documento de identidad') || texto.toLowerCase().includes('identidad')) {
                break;
              }
            }
          }
          if (!target) {
            // label[for] / texto hermano
            const labels = Array.from(document.querySelectorAll('label, td, span, div'));
            for (const lab of labels) {
              const t = (lab.innerText || '').trim().toLowerCase();
              if (!t.includes(texto.toLowerCase())) continue;
              const inLab = lab.querySelector('input[type=checkbox]');
              if (inLab) { target = inLab; break; }
              const prev = lab.previousElementSibling;
              if (prev && prev.matches && prev.matches('input[type=checkbox]')) { target = prev; break; }
              const next = lab.nextElementSibling;
              if (next && next.matches && next.matches('input[type=checkbox]')) { target = next; break; }
            }
          }
          if (!target) return { ok: false, reason: 'no-cb', n: inputs.length };
          target.focus();
          target.checked = !!marcar;
          target.dispatchEvent(new Event('click', { bubbles: true }));
          target.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: true, checked: !!target.checked, name: target.name || '', id: target.id || '' };
        }
        """
        for scope in self._scopes(page):
            try:
                res = scope.evaluate(js, [texto, marcar])
                if isinstance(res, dict) and res.get("ok"):
                    wanted = bool(marcar)
                    if bool(res.get("checked")) == wanted:
                        log.info(
                            "Checkbox «%s» → %s (js name=%s id=%s)",
                            texto,
                            "ON" if wanted else "OFF",
                            res.get("name"),
                            res.get("id"),
                        )
                        return True
            except Exception as exc:
                log.debug("JS checkbox %s: %s", texto, exc)

            # Playwright: fila con el texto → checkbox
            try:
                filas = scope.locator("tr, label, li, div").filter(has_text=label_rx)
                n = min(filas.count(), 8)
                for i in range(n):
                    fila = filas.nth(i)
                    cbs = fila.locator("input[type='checkbox']")
                    if not cbs.count():
                        continue
                    cb = cbs.first
                    if not cb.is_visible():
                        continue
                    # Evitar filas enormes que contienen todo el formulario
                    try:
                        txt = (fila.inner_text(timeout=800) or "").strip()
                        if len(txt) > 120:
                            continue
                    except Exception:
                        pass
                    try:
                        if marcar:
                            if not cb.is_checked():
                                cb.check(force=True, timeout=5000)
                        else:
                            if cb.is_checked():
                                cb.uncheck(force=True, timeout=5000)
                        log.info("Checkbox «%s» → %s (playwright)", texto, "ON" if marcar else "OFF")
                        return True
                    except Exception:
                        try:
                            cb.click(force=True, timeout=5000)
                            log.info("Checkbox «%s» clic (playwright)", texto)
                            return True
                        except Exception:
                            continue
            except Exception:
                continue

            # get_by_label / role
            try:
                loc = scope.get_by_label(label_rx)
                if loc.count():
                    el = loc.first
                    if marcar and not el.is_checked():
                        el.check(force=True, timeout=5000)
                    elif not marcar and el.is_checked():
                        el.uncheck(force=True, timeout=5000)
                    return True
            except Exception:
                pass
            try:
                loc = scope.get_by_role("checkbox", name=label_rx)
                if loc.count():
                    el = loc.first
                    if marcar and not el.is_checked():
                        el.check(force=True, timeout=5000)
                    elif not marcar and el.is_checked():
                        el.uncheck(force=True, timeout=5000)
                    return True
            except Exception:
                pass

        return False

    def _click_boton_en_scopes(self, page: Page, nombre_rx: str) -> bool:
        pat = re.compile(str(nombre_rx), re.I)
        for scope in self._scopes(page):
            for role in ("button", "link"):
                try:
                    b = scope.get_by_role(role, name=pat)
                    if b.count():
                        b.first.click(timeout=8000, force=True)
                        return True
                except Exception:
                    continue
            try:
                b = scope.locator(
                    "input[type='submit'], input[type='button'], button, a"
                ).filter(has_text=pat)
                if b.count():
                    b.first.click(timeout=8000, force=True)
                    return True
            except Exception:
                continue
        return self._click_por_nombre(page, nombre_rx)

    def _recepcionar_documentacion(self, page: Page) -> None:
        page = self._page_activa()
        # Esperar pantalla de recepción (puede estar en iframe)
        try:
            page = self._esperar_ui(
                lambda p: "recepcionar" in self.identificar_pantalla(p)
                or "documento de identidad" in self._page_text(p),
                timeout_ms=15000,
                desc="Recepcionar Documentación",
            )
        except Exception:
            page = self._page_activa()

        check_txt = str(self._sel("recepcion", "check_documento", default="DOCUMENTO DE IDENTIDAD"))
        log.info("Recepcionar: marcar «%s»", check_txt)

        ok = self._marcar_checkbox_por_texto(page, check_txt, marcar=True)
        if not ok:
            # Variantes de texto (asterisco / mayúsculas)
            for alt in (
                "DOCUMENTO DE IDENTIDAD",
                "*DOCUMENTO DE IDENTIDAD",
                "Documento de Identidad",
            ):
                if self._marcar_checkbox_por_texto(page, alt, marcar=True):
                    ok = True
                    break
        if not ok:
            raise RuntimeError(
                "No pude marcar el check DOCUMENTO DE IDENTIDAD en Recepcionar Documentación. "
                "Deje esa pantalla visible y vuelva a enviar."
            )

        # Asegurar que PODER / FACTURA queden sin marcar
        for no in self._sel("recepcion", "no_marcar", default=["PODER", "FACTURA LUZ/AGUA"]) or []:
            try:
                self._marcar_checkbox_por_texto(page, str(no), marcar=False)
            except Exception:
                pass

        grabar = self._sel("recepcion", "boton_grabar", default="^Grabar$")
        if not self._click_boton_en_scopes(page, str(grabar)):
            raise RuntimeError("No se encontró botón Grabar en Recepcionar Documentación")
        log.info("Recepcionar: Grabar OK")
        page.wait_for_timeout(1000)

    def _datos_generales(self, page: Page, doc: dict) -> None:
        page = self._page_activa()
        try:
            page = self._esperar_ui(
                lambda p: self.identificar_pantalla(p) == "datos_generales"
                or "datos generales" in self._page_text(p),
                timeout_ms=12000,
                desc="Datos Generales",
            )
        except Exception:
            page = self._page_activa()

        dg = self.selectors.get("datos_generales") or {}
        self._fill_if_empty(page, dg.get("nombres", r"Nombre\(s\)|Nombres"), doc.get("nombres") or "")
        self._fill_if_empty(
            page, dg.get("primer_apellido", "Primer Apellido"), doc.get("primer_apellido") or ""
        )
        self._fill_if_empty(
            page, dg.get("segundo_apellido", "Segundo Apellido"), doc.get("segundo_apellido") or ""
        )

        genero = (doc.get("genero") or "").upper()
        if "FEM" in genero:
            g_label = str(dg.get("genero_femenino", "FEMENINO"))
        elif genero:
            g_label = str(dg.get("genero_masculino", "MASCULINO"))
        else:
            g_label = ""
        if g_label:
            if not self._marcar_checkbox_por_texto(page, g_label, marcar=True):
                # A veces es radio
                for scope in self._scopes(page):
                    try:
                        t = scope.get_by_text(re.compile(rf"^{re.escape(g_label)}$", re.I))
                        if t.count():
                            t.first.click(force=True, timeout=4000)
                            break
                    except Exception:
                        continue

        ec_raw = (doc.get("estado_civil") or "").upper().strip()
        ec_map = dg.get("estado_civil_map") or {}
        ec = ec_map.get(ec_raw) or ec_map.get(ec_raw.replace("(A)", "")) or ec_raw
        if ec:
            if not self._select_por_label(page, str(dg.get("estado_civil", "Estado Civil")), str(ec)):
                log.warning("No se pudo seleccionar estado civil %s", ec)

        fecha = self._normalizar_fecha_dd_mm_aaaa(doc.get("fecha_nacimiento") or "")
        self._fill_if_empty(page, dg.get("fecha_nacimiento", "Fecha Nacimiento"), fecha)

        aceptar = dg.get("boton_aceptar", "^Aceptar$")
        if not self._click_boton_en_scopes(page, str(aceptar)):
            raise RuntimeError("No se encontró botón Aceptar en Datos Generales")
        log.info("Datos Generales → Aceptar OK")
        page.wait_for_timeout(800)

    @staticmethod
    def _normalizar_fecha_dd_mm_aaaa(valor: str) -> str:
        v = (valor or "").strip()
        if not v:
            return ""
        # Ya DD/MM/AAAA
        if re.match(r"^\d{2}/\d{2}/\d{4}$", v):
            return v
        # AAAA-MM-DD
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        # DD-MM-AAAA
        m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", v)
        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        return v

    def _domicilio_legal(self, page: Page, doc: dict) -> None:
        page = self._page_activa()
        dom = self.selectors.get("domicilio") or {}

        ba = dom.get("busqueda_avanzada") or {}
        if ba.get("obligatorio", True):
            name = ba.get("link_name", "Búsqueda Avanzada")
            opened = False
            for scope in self._scopes(page):
                try:
                    link = scope.get_by_role("link", name=re.compile(str(name), re.I))
                    if link.count() == 0:
                        link = scope.get_by_text(re.compile(str(name), re.I))
                    if link.count():
                        link.first.click(timeout=8000, force=True)
                        opened = True
                        break
                except Exception:
                    continue
            if not opened:
                raise RuntimeError("No se encontró link Búsqueda Avanzada en Domicilio Legal")
            page.wait_for_timeout(900)
            log.info("Abierta Búsqueda Avanzada de domicilio")
            self._domicilio_busqueda_avanzada(self._page_activa(), doc)

        page = self._page_activa()
        puerta = (doc.get("numero_puerta") or "").strip()
        label_puerta = dom.get("numero_puerta", "Número Puerta")
        label_sin = str(dom.get("sin_numero", "Sin Número"))

        if puerta and puerta.upper() not in {"S/N", "SN", "SIN NUMERO", "SIN NÚMERO"}:
            self._marcar_checkbox_por_texto(page, label_sin, marcar=False)
            self._fill_if_empty(page, str(label_puerta), puerta)
            log.info("Número Puerta desde CI: %s", puerta)
        else:
            if not self._marcar_checkbox_por_texto(page, label_sin, marcar=True):
                log.warning("No se pudo marcar Sin Número")
            log.info("Sin número de puerta en CI → marcado Sin Número")

        aceptar = dom.get("boton_aceptar", "^Aceptar$")
        if not self._click_boton_en_scopes(page, str(aceptar)):
            raise RuntimeError("No se encontró botón Aceptar en Domicilio Legal")
        log.info("Domicilio Legal → Aceptar OK")
        page.wait_for_timeout(800)

    def _domicilio_busqueda_avanzada(self, page: Page, doc: dict) -> None:
        """
        BUSQUEDA AVANZADA DIRECCION (Riberalta):
        1) URBANO + Tipo=AVENIDA + Nombre=avenida del CI → Buscar
        2) En Resultados: Asociar fila con MISMO barrio Y MISMA avenida del CI
        3) Si no hay esa fila → Nombre=SIN NOMINAR → Buscar → Asociar BARRIO SIN NOMINAR + AVENIDA SIN NOMINAR
        """
        page = self._page_activa()
        ba = (self.selectors.get("domicilio") or {}).get("busqueda_avanzada_form") or {}
        avenida = (doc.get("avenida") or "").strip()
        barrio = (doc.get("barrio") or "").strip()
        fallback = str(ba.get("fallback_nombre") or "SIN NOMINAR")
        tipo = str(ba.get("tipo_lugar") or "AVENIDA")
        area = str(ba.get("area_default") or "URBANO")
        btn_buscar = str(ba.get("boton_buscar") or "^Buscar$")

        if not self._marcar_checkbox_por_texto(page, area, marcar=True):
            for scope in self._scopes(page):
                try:
                    t = scope.get_by_text(re.compile(rf"^{re.escape(area)}$", re.I))
                    if t.count():
                        t.first.click(force=True, timeout=4000)
                        break
                except Exception:
                    continue

        label_tipo = ba.get("label_tipo_lugar", "Tipo Lugar")
        if not self._select_por_label(page, str(label_tipo), tipo):
            log.warning("No se pudo seleccionar Tipo Lugar=%s", tipo)

        label_nombre = ba.get("label_nombre_lugar", "Nombre Lugar")

        def _set_nombre(valor: str) -> None:
            if not self._fill_if_empty(page, str(label_nombre), valor):
                # Forzar aunque no esté vacío
                for scope in self._scopes(page):
                    try:
                        loc = scope.get_by_label(re.compile(str(label_nombre), re.I))
                        if loc.count():
                            self._escribir_en_input(loc.first, valor, page)
                            return
                    except Exception:
                        continue
                raise RuntimeError(f"No se pudo escribir Nombre Lugar={valor}")

        def _click_buscar() -> None:
            if not self._click_boton_en_scopes(page, btn_buscar):
                raise RuntimeError("No se encontró Buscar en Búsqueda Avanzada")
            page.wait_for_timeout(1200)

        if not avenida:
            log.warning("Sin avenida OCR → directo a SIN NOMINAR")
        else:
            _set_nombre(avenida)
            _click_buscar()
            if self._domicilio_asociar_barrio_avenida(self._page_activa(), barrio=barrio, avenida=avenida):
                log.info("Asociado barrio='%s' avenida='%s'", barrio, avenida)
                return
            log.info(
                "No hay fila con barrio='%s' y avenida='%s' → fallback SIN NOMINAR",
                barrio,
                avenida,
            )

        _set_nombre(fallback)
        _click_buscar()
        if self._domicilio_asociar_sin_nominar(self._page_activa()):
            log.info("Asociado BARRIO SIN NOMINAR + AVENIDA SIN NOMINAR")
            return

        raise RuntimeError(
            "No se pudo asociar dirección (ni barrio+avenida del CI ni SIN NOMINAR)."
        )

    def _domicilio_asociar_barrio_avenida(self, page: Page, *, barrio: str, avenida: str) -> bool:
        """En la tabla Resultados, Asociar solo si coinciden barrio y avenida del CI."""
        ba = (self.selectors.get("domicilio") or {}).get("busqueda_avanzada_form") or {}
        asociar_re = str(ba.get("link_asociar") or "^Asociar$")
        if not avenida:
            return False

        barrio_norm = self._norm_lugar(barrio)
        for scope in self._scopes(page):
            try:
                rows = scope.locator("table").locator("tr").filter(
                    has_text=re.compile(re.escape(avenida), re.I)
                )
                if rows.count() == 0:
                    rows = scope.locator("tr").filter(has_text=re.compile(re.escape(avenida), re.I))
                if rows.count() == 0:
                    continue
                for i in range(min(rows.count(), 40)):
                    row = rows.nth(i)
                    try:
                        text = row.inner_text(timeout=800) or ""
                    except Exception:
                        continue
                    if avenida.upper() not in text.upper():
                        continue
                    if barrio_norm and barrio_norm not in self._norm_lugar(text):
                        continue
                    link = row.get_by_role("link", name=re.compile(asociar_re, re.I))
                    if link.count() == 0:
                        link = row.get_by_text(re.compile(asociar_re, re.I))
                    if link.count():
                        link.first.click(timeout=8000, force=True)
                        page.wait_for_timeout(900)
                        return True
            except Exception:
                continue

        if not barrio_norm:
            log.warning("Hay resultados de avenida pero sin barrio OCR para emparejar")
        return False

    def _domicilio_asociar_sin_nominar(self, page: Page) -> bool:
        ba = (self.selectors.get("domicilio") or {}).get("busqueda_avanzada_form") or {}
        asociar_re = str(ba.get("link_asociar") or "^Asociar$")
        for scope in self._scopes(page):
            try:
                rows = scope.locator("tr").filter(has_text=re.compile(r"SIN\s*NOMINAR", re.I))
                prefer = rows.filter(has_text=re.compile(r"BARRIO", re.I)).filter(
                    has_text=re.compile(r"AVENIDA", re.I)
                )
                target = prefer if prefer.count() else rows
                for i in range(min(target.count(), 20)):
                    row = target.nth(i)
                    link = row.get_by_role("link", name=re.compile(asociar_re, re.I))
                    if link.count() == 0:
                        link = row.get_by_text(re.compile(asociar_re, re.I))
                    if link.count():
                        link.first.click(timeout=8000, force=True)
                        page.wait_for_timeout(900)
                        return True
            except Exception:
                continue
        return False

    @staticmethod
    def _norm_lugar(valor: str) -> str:
        v = (valor or "").upper()
        v = v.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
        v = re.sub(r"\bURB\.?\b", " ", v)
        v = re.sub(r"\s+", " ", v).strip()
        return v

    def _cancelar_apoderado(self, page: Page) -> None:
        """
        Tras Aceptar domicilio aparece:
        «¿Desea registrar un Apoderado/Representante Legal?» → siempre Cancelar.
        Suele ser confirm nativo (manejado por _on_browser_dialog); esto es respaldo HTML.
        """
        page = self._page_activa()
        page.wait_for_timeout(500)
        name = self._sel("apoderado", "boton_cancelar", default="^Cancelar$")

        has_prompt = False
        for scope in self._scopes(page):
            try:
                if scope.get_by_text(re.compile(r"Apoderado|Representante\s*Legal", re.I)).count():
                    has_prompt = True
                    break
            except Exception:
                continue
        if not has_prompt:
            log.info("Sin prompt de apoderado visible (posible dismiss nativo ya aplicado)")
            return

        if self._click_boton_en_scopes(page, str(name)):
            page.wait_for_timeout(500)
            log.info("Apoderado → Cancelar")
            return

        for scope in self._scopes(page):
            try:
                dialog = scope.get_by_role("dialog")
                if dialog.count():
                    cancelar = dialog.get_by_role("button", name=re.compile(str(name), re.I))
                    if cancelar.count():
                        cancelar.first.click(force=True, timeout=5000)
                        page.wait_for_timeout(500)
                        log.info("Apoderado → Cancelar (HTML dialog)")
                        return
            except Exception:
                continue
        log.warning("Prompt de apoderado visible pero no se pudo Cancelar")

    def _info_adicional(self, page: Page, doc: dict) -> None:
        """Solo *Teléfono Celular (aleatorio de la API); resto en blanco → Aceptar."""
        page = self._page_activa()
        info = self.selectors.get("info_adicional") or {}
        celular = (doc.get("telefono_celular") or "").strip() or "78998541"
        label = info.get("celular", r"Teléfono Celular|Telefono Celular")
        if not self._fill_if_empty(page, str(label), celular):
            # Forzar overwrite
            for scope in self._scopes(page):
                try:
                    loc = scope.get_by_label(re.compile(str(label), re.I))
                    if loc.count():
                        self._escribir_en_input(loc.first, celular, page)
                        break
                except Exception:
                    continue
        log.info("Celular aleatorio: %s", celular)

        aceptar = info.get("boton_aceptar", "^Aceptar$")
        if not self._click_boton_en_scopes(page, str(aceptar)):
            raise RuntimeError("No se encontró botón Aceptar en Información Adicional")
        page.wait_for_timeout(700)

    def _subir_fotografia(self, page: Page, doc: dict) -> None:
        """Solo sección Fotografía (≤90 KB). Sin foto_url → continúa sin foto."""
        page = self._page_activa()
        img = self.selectors.get("imagenes") or {}
        foto_cfg = img.get("fotografia") or {}
        url = doc.get("foto_url")
        if not url:
            log.warning("Sin foto_url — continúo sin fotografía")
            self._aceptar_registrar_imagenes(page, img)
            return
        dest = self.download_dir / f"{doc['id']}-foto.jpg"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)
        size = dest.stat().st_size
        max_kb = int(foto_cfg.get("max_kb") or 90)
        if size > max_kb * 1024:
            log.warning("Foto pesa %s bytes (>%sKB). RUAT puede rechazarla.", size, max_kb)
        else:
            log.info("Foto descargada (%s bytes)", size)

        idx = int(foto_cfg.get("input_file_index", 0) or 0)
        file_input = None
        for scope in self._scopes(page):
            try:
                seccion = scope.locator("tr, div, table").filter(
                    has_text=re.compile(r"Fotogra", re.I)
                ).filter(has=scope.locator("input[type='file']"))
                if seccion.count():
                    cand = seccion.first.locator("input[type='file']").first
                    if cand.count():
                        file_input = cand
                        break
            except Exception:
                continue
        if file_input is None or file_input.count() == 0:
            css = img.get("input_file", "input[type='file']")
            for scope in self._scopes(page):
                try:
                    cand = scope.locator(str(css)).nth(idx)
                    if cand.count():
                        file_input = cand
                        break
                except Exception:
                    continue
        if file_input is None or file_input.count() == 0:
            raise RuntimeError("No se encontró input Examinar de Fotografía")

        file_input.set_input_files(str(dest))
        page.wait_for_timeout(800)
        log.info("Fotografía del escaneo inyectada (sin diálogo Windows): %s", dest.name)

        self._editar_fotografia_procesar(self._page_activa())
        self._aceptar_registrar_imagenes(self._page_activa(), img)

    def _aceptar_registrar_imagenes(self, page: Page, img: dict | None = None) -> None:
        img = img or (self.selectors.get("imagenes") or {})
        page = self._page_activa()
        page.wait_for_timeout(500)
        aceptar = img.get("boton_aceptar", "^Aceptar$")
        if self._click_boton_en_scopes(page, str(aceptar)):
            page.wait_for_timeout(1000)
            log.info("Registrar Imágenes → Aceptar")
        else:
            log.warning("No se encontró Aceptar en Registrar Imágenes — continúo")

    def _confirmar_tramite_imprimir(self, page: Page) -> None:
        """
        CONFIRMAR TRAMITE — Pasos Finales:
        1) Imprimir Reporte  ← agente
        2) Grabar            ← NO (modo seguro: operador)
        3) Salir             ← operador
        """
        page = self._page_activa()
        conf = self.selectors.get("confirmar_tramite") or {}
        page.wait_for_timeout(600)

        imprimir_rx = str(conf.get("boton_imprimir", r"^Imprimir\s+Reporte$"))
        clicked = self._click_boton_en_scopes(page, imprimir_rx)
        if not clicked:
            for scope in self._scopes(page):
                try:
                    t = scope.get_by_text(re.compile(r"Imprimir\s+Reporte", re.I))
                    if t.count():
                        t.first.click(force=True, timeout=8000)
                        clicked = True
                        break
                except Exception:
                    continue
        if not clicked:
            raise RuntimeError("No se encontró botón Imprimir Reporte")

        page.wait_for_timeout(800)
        log.info("CONFIRMAR TRAMITE → Imprimir Reporte (modo seguro: sin Grabar)")
        log.info(
            ">>> OPERADOR: revise el Reporte de Control de Datos, confirme con el contribuyente "
            "y pulse Grabar en RUAT. Luego Salir."
        )

        if os.getenv("GRABAR_AUTOMATICO", "").strip().lower() in {"1", "true", "yes"}:
            grabar = str(conf.get("boton_grabar", "^Grabar$"))
            if self._click_boton_en_scopes(page, grabar):
                page.wait_for_timeout(1000)
                log.info("Fase 2: Grabar automático activado")
            else:
                log.warning("GRABAR_AUTOMATICO=1 pero no se encontró botón Grabar")
        else:
            log.info("Modo seguro MVP: Grabar/Salir quedan para el operador (Fase 2: GRABAR_AUTOMATICO=1)")

    def _editar_fotografia_procesar(self, page: Page) -> None:
        """
        Pantalla EDITAR FOTOGRAFÍA: cuadro remarcado = área a conservar.
        MVP: si RUAT ya dibuja un recorte razonable, Pulsar Procesar.
        """
        page = self._page_activa()
        edit = (self.selectors.get("imagenes") or {}).get("editar_fotografia") or {}
        page.wait_for_timeout(600)
        procesar_rx = str(edit.get("boton_procesar", "^Procesar$"))

        en_edicion = False
        has_proc = False
        for scope in self._scopes(page):
            try:
                if scope.get_by_text(re.compile(r"EDITAR\s+FOTOGRAF", re.I)).count():
                    en_edicion = True
                if scope.get_by_role("button", name=re.compile(procesar_rx, re.I)).count():
                    has_proc = True
            except Exception:
                continue

        if not en_edicion and not has_proc:
            log.info("No apareció EDITAR FOTOGRAFÍA — se continúa")
            return

        log.info("EDITAR FOTOGRAFÍA: usando cuadro remarcado (default RUAT) → Procesar")
        if not self._click_boton_en_scopes(page, procesar_rx):
            raise RuntimeError("No se encontró botón Procesar en Editar Fotografía")
        page.wait_for_timeout(1200)

        finalizar_rx = str(edit.get("boton_finalizar", "^Finalizar$"))
        if self._click_boton_en_scopes(self._page_activa(), finalizar_rx):
            page.wait_for_timeout(1000)
            log.info("Fotografía enmarcada → Finalizar")
        else:
            raise RuntimeError("No se encontró botón Finalizar tras Procesar la fotografía")

    def _fill_if_empty(self, page: Page, label_pattern: str, value: str) -> bool:
        """Rellena input vacío por label (página + iframes). Devuelve True si escribió."""
        if not value:
            return False
        label_rx = re.compile(str(label_pattern), re.I)
        css = "input[type='text'], input:not([type]), input[type=''], input[type='search'], input[type='tel']"

        for scope in self._scopes(page):
            # 1) get_by_label
            try:
                loc = scope.get_by_label(label_rx)
                if loc.count():
                    el = loc.first
                    try:
                        current = (el.input_value(timeout=1500) or "").strip()
                    except Exception:
                        current = ""
                    if current:
                        return True
                    if self._escribir_en_input(el, value, page):
                        return True
            except Exception:
                pass

            # 2) Fila con el texto del label → input
            try:
                filas = scope.locator("tr, label, div, td").filter(has_text=label_rx)
                n = min(filas.count(), 6)
                for i in range(n):
                    fila = filas.nth(i)
                    try:
                        txt = (fila.inner_text(timeout=600) or "").strip()
                        if len(txt) > 100:
                            continue
                    except Exception:
                        continue
                    el = self._input_texto_visible(fila, css, 0)
                    if el is None:
                        continue
                    try:
                        current = (el.input_value(timeout=1500) or "").strip()
                    except Exception:
                        current = ""
                    if current:
                        return True
                    if self._escribir_en_input(el, value, page):
                        return True
            except Exception:
                continue

        # 3) JS por frames
        js = """
        ([labelRe, valor]) => {
          const re = new RegExp(labelRe, 'i');
          const okType = (t) => {
            t = (t || 'text').toLowerCase();
            return ['text','','search','tel','number'].includes(t);
          };
          const inputs = Array.from(document.querySelectorAll('input')).filter(
            (i) => okType(i.type) && i.offsetParent !== null && !i.disabled
          );
          for (const inp of inputs) {
            const row = inp.closest('tr') || inp.parentElement;
            const txt = ((row && row.innerText) || '');
            if (!re.test(txt)) continue;
            if ((inp.value || '').trim()) return { ok: true, already: true, value: inp.value };
            inp.focus();
            inp.value = valor;
            for (const ev of ['input', 'change', 'keyup']) {
              try { inp.dispatchEvent(new Event(ev, { bubbles: true })); } catch (e) {}
            }
            return { ok: true, value: inp.value, name: inp.name || '' };
          }
          return { ok: false };
        }
        """
        # Convertir patrón tipo Nombre\\(s\\)|Nombres a string usable en RegExp JS (simple)
        label_js = str(label_pattern).replace("\\\\", "\\")
        for scope in self._scopes(page):
            try:
                res = scope.evaluate(js, [label_js, value])
                if isinstance(res, dict) and res.get("ok"):
                    log.info("Campo «%s» escrito (js) → %r", label_pattern, res.get("value"))
                    return True
            except Exception:
                continue

        log.warning("Campo no encontrado o no escrito: %s", label_pattern)
        return False

    def _select_por_label(self, page: Page, label_pattern: str, option_label: str) -> bool:
        """Selecciona opción en <select> por label (scopes)."""
        label_rx = re.compile(str(label_pattern), re.I)
        opt_rx = re.compile(re.escape(str(option_label).split("(")[0]), re.I)
        for scope in self._scopes(page):
            try:
                sel = scope.get_by_label(label_rx)
                if sel.count() == 0:
                    continue
                try:
                    sel.first.select_option(label=opt_rx, timeout=5000)
                    return True
                except Exception:
                    try:
                        sel.first.select_option(label=str(option_label), timeout=5000)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        # Fallback: select que contenga la opción
        for scope in self._scopes(page):
            try:
                sel = scope.locator("select").filter(has_text=opt_rx)
                if sel.count():
                    sel.first.select_option(label=opt_rx, timeout=5000)
                    return True
            except Exception:
                continue
        return False

    def _esperar_alguna_pantalla(self, destinos: tuple[str, ...] | list[str], timeout_ms: int = 15000) -> bool:
        """Espera hasta que identificar_pantalla sea uno de destinos."""
        deadline = time.time() + timeout_ms / 1000.0
        wanted = set(destinos)
        while time.time() < deadline:
            page = self._page_activa()
            pant = self.identificar_pantalla(page)
            if pant in wanted:
                return True
            try:
                page.wait_for_timeout(400)
            except Exception:
                time.sleep(0.4)
        return False

    def _ejecutar_paso(
        self,
        paso: str,
        accion,
        destinos: tuple[str, ...] | list[str],
        *,
        max_intentos: int = 3,
        recuperar_menu: bool = False,
    ) -> Page:
        """
        Ejecuta un paso con reintentos y verificación de pantalla destino.
        Si falla: RuntimeError con paso + pantalla (para la API).
        """
        self._paso_actual = paso
        last_err: Exception | None = None
        for intento in range(1, max_intentos + 1):
            page = self._page_activa()
            pant = self.identificar_pantalla(page)
            self._ultima_pantalla = pant
            log.info(
                "paso=%s intento=%s/%s pantalla=%s url=%s",
                paso,
                intento,
                max_intentos,
                pant,
                (page.url or "")[:100],
            )
            try:
                accion()
                if self._esperar_alguna_pantalla(destinos, timeout_ms=16000):
                    page = self._page_activa()
                    self._ultima_pantalla = self.identificar_pantalla(page)
                    log.info("paso=%s OK → pantalla=%s", paso, self._ultima_pantalla)
                    return page
                pant_after = self.identificar_pantalla(self._page_activa())
                last_err = RuntimeError(
                    f"Tras «{paso}» esperaba {list(destinos)} y quedé en «{pant_after}»"
                )
                log.warning("%s", last_err)
            except Exception as exc:
                last_err = exc
                log.warning("Fallo paso «%s»: %s", paso, exc)

            if intento < max_intentos and recuperar_menu:
                try:
                    log.info("Recuperación: forzando menú principal…")
                    self._forzar_menu_principal()
                except Exception as rec:
                    log.warning("No se pudo forzar menú: %s", rec)

        page = self._page_activa()
        pant = self.identificar_pantalla(page)
        self._ultima_pantalla = pant
        detalle = str(last_err) if last_err else "sin detalle"
        raise RuntimeError(
            f"Paso «{paso}» falló (pantalla={pant}). "
            "Cierre el trámite a medias en RUAT o vuelva al menú principal y use Reintentar envío. "
            f"Detalle: {detalle[:280]}"
        )
