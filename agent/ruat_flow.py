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
from pathlib import Path
from typing import Any

import requests
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

log = logging.getLogger("ruat")

SELECTORS_PATH = Path(__file__).with_name("selectors.json")


class ContribuyenteYaRegistrado(Exception):
    """CI ya existe en el mismo municipio (ej. RIBERALTA): no continuar el alta."""

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
        self.ruat_url = os.getenv("RUAT_START_URL", "").strip()
        self.mode = (os.getenv("FIREFOX_MODE") or "persistent").strip().lower()

    def connect(self) -> None:
        self._pw = sync_playwright().start()
        if self.mode == "connect_cdp":
            self._connect_cdp()
        elif self.mode == "launch":
            self._connect_launch()
        else:
            self._connect_persistent()

        assert self.page is not None
        # Diálogos nativos del navegador (confirm): siempre Cancelar si preguntan por Apoderado
        self.page.on("dialog", self._on_browser_dialog)
        if self.ruat_url and self.ruat_url not in (self.page.url or ""):
            log.info("Navegando a RUAT_START_URL…")
            self.page.goto(self.ruat_url, wait_until="domcontentloaded")
        log.info("Firefox listo · mode=%s · url=%s", self.mode, self.page.url)

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

    def _pick_page(self, context: BrowserContext) -> Page:
        pages = context.pages
        if self.ruat_url:
            host = re.sub(r"^https?://", "", self.ruat_url).split("/")[0].lower()
            for p in pages:
                if host and host in (p.url or "").lower():
                    p.bring_to_front()
                    return p
        if pages:
            pages[0].bring_to_front()
            return pages[0]
        return context.new_page()

    def close(self) -> None:
        try:
            if self.mode == "persistent" and self._context:
                self._context.close()
            elif self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def procesar(self, doc: dict) -> None:
        assert self.page is not None
        page = self.page

        if self.dry_run:
            log.info(
                "[DRY_RUN] CI=%s nombres=%s foto=%s",
                doc.get("numero_documento"),
                doc.get("nombres"),
                bool(doc.get("foto_url")),
            )
            return

        self._ir_contribuyente_natural(page)
        self._ir_registro_contribuyente_natural(page)
        self._buscar_contribuyente(page, doc)

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
        if rama == "asociar":
            log.info("Coincidencia en otro municipio → Asociar (sin marcar foto)")
            self._click_asociar_mejor_nombre(page, doc)
        else:
            log.info("Sin registro usable → Nuevo Contribuyente / alta nueva")
            self._click_nuevo_contribuyente(page)

        self._recepcionar_documentacion(page)
        self._datos_generales(page, doc)
        self._domicilio_legal(page, doc)
        self._cancelar_apoderado(page)
        self._info_adicional(page, doc)
        self._subir_fotografia(page, doc)
        self._confirmar_tramite_imprimir(page)
        log.info("Flujo RUAT completado (modo seguro — NO se pulsó Grabar)")

    # --- pasos ---

    def _sel(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.selectors
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def _ir_contribuyente_natural(self, page: Page) -> None:
        name = self._sel("contribuyente_natural", "link_name", default="Contribuyente Natural")
        link = page.get_by_role("link", name=re.compile(str(name), re.I))
        if link.count():
            link.first.click()
            page.wait_for_timeout(700)
        else:
            log.warning("No se encontró '%s' — asuma que ya está en el submenú", name)

    def _ir_registro_contribuyente_natural(self, page: Page) -> None:
        name = self._sel(
            "registro_contribuyente_natural",
            "link_name",
            default="^Registro Contribuyente Natural$",
        )
        link = page.get_by_role("link", name=re.compile(str(name), re.I))
        if link.count():
            link.first.click()
            page.wait_for_timeout(900)
        else:
            log.warning(
                "No se encontró '%s' — asuma que ya está en Buscar Contribuyente",
                name,
            )

    def _buscar_contribuyente(self, page: Page, doc: dict) -> None:
        numero = (doc.get("numero_documento") or "").split("-")[0].strip()
        if not numero:
            raise RuntimeError("numero_documento vacío")

        # Número Documento: caja grande; complemento (después del "-") se deja vacío
        label_doc = self._sel("buscar", "label_documento", default="Número Documento")
        filled = False
        try:
            by_label = page.get_by_label(re.compile(str(label_doc), re.I))
            if by_label.count():
                by_label.first.fill(numero)
                filled = True
        except Exception:
            pass
        if not filled:
            css = self._sel("buscar", "input_documento", default="input[type='text']")
            idx = int(self._sel("buscar", "input_documento_index", default=0) or 0)
            page.locator(str(css)).nth(idx).fill(numero)

        # Tipo Documento = CEDULA DE IDENTIDAD (suele venir ya seleccionado)
        tipo_label = self._sel("buscar", "tipo_documento_label", default="CEDULA DE IDENTIDAD")
        label_tipo = self._sel("buscar", "label_tipo_documento", default="Tipo Documento")
        tipo = page.get_by_label(re.compile(str(label_tipo), re.I))
        if tipo.count() == 0:
            tipo = page.locator("select").filter(has_text=re.compile(r"CEDULA|IDENTIDAD", re.I))
        if tipo.count():
            try:
                tipo.first.select_option(label=re.compile(str(tipo_label), re.I))
            except Exception:
                log.warning("No se pudo fijar tipo documento %s (puede ya estar seleccionado)", tipo_label)

        # Departamento Expedido → opción en blanco (regla fija Riberalta/RUAT)
        label_depto = self._sel("buscar", "label_departamento", default="Departamento Expedido")
        depto = page.get_by_label(re.compile(str(label_depto), re.I))
        if depto.count() == 0:
            depto = page.locator("select").nth(1)
        if depto.count():
            try:
                # Preferir valor vacío / primera opción en blanco
                depto.first.select_option(index=0)
                log.info("Departamento Expedido dejado en blanco (índice 0)")
            except Exception:
                log.warning("No se pudo forzar Departamento Expedido en blanco")

        btn = self._sel("buscar", "boton_buscar", default="^Buscar$")
        page.get_by_role("button", name=re.compile(str(btn), re.I)).click()
        page.wait_for_timeout(1000)

    def _clasificar_resultado_busqueda(self, page: Page) -> str:
        """
        Tras Buscar:
        - ya_en_municipio: Resultados con Gobierno Municipal = RIBERALTA
        - asociar: link Asociar (otro municipio)
        - nuevo: Nuevo Contribuyente / sin fila local
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

    def _recepcionar_documentacion(self, page: Page) -> None:
        check_txt = self._sel("recepcion", "check_documento", default="DOCUMENTO DE IDENTIDAD")
        # Preferir checkbox asociado al texto DOCUMENTO DE IDENTIDAD
        row = page.get_by_text(re.compile(str(check_txt), re.I))
        if row.count():
            # Si es label, clic; si hay checkbox cerca, marcarlo
            try:
                cb = page.locator("input[type='checkbox']").first
                # Buscar checkbox en la misma fila que el texto
                near = page.locator(
                    f"xpath=//*[contains(translate(., 'identidad', 'IDENTIDAD'), 'DOCUMENTO DE IDENTIDAD')]/ancestor::tr[1]//input[@type='checkbox'] | //label[contains(., 'DOCUMENTO DE IDENTIDAD')]//input[@type='checkbox']"
                )
                if near.count():
                    if not near.first.is_checked():
                        near.first.check(force=True)
                else:
                    row.first.click()
            except Exception:
                row.first.click()
        # No marcar PODER / FACTURA; no usar Registrar tramitador (Gestor Trámite eliminado)
        grabar = self._sel("recepcion", "boton_grabar", default="^Grabar$")
        btn = page.get_by_role("button", name=re.compile(str(grabar), re.I))
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(800)
        else:
            raise RuntimeError("No se encontró botón Grabar en Recepcionar Documentación")

    def _datos_generales(self, page: Page, doc: dict) -> None:
        dg = self.selectors.get("datos_generales") or {}
        self._fill_if_empty(page, dg.get("nombres", r"Nombre\(s\)|Nombres"), doc.get("nombres") or "")
        self._fill_if_empty(
            page, dg.get("primer_apellido", "Primer Apellido"), doc.get("primer_apellido") or ""
        )
        self._fill_if_empty(
            page, dg.get("segundo_apellido", "Segundo Apellido"), doc.get("segundo_apellido") or ""
        )
        # Apellido Esposo: no llenar en MVP

        genero = (doc.get("genero") or "").upper()
        if "FEM" in genero:
            g_label = dg.get("genero_femenino", "FEMENINO")
        elif genero:
            g_label = dg.get("genero_masculino", "MASCULINO")
        else:
            g_label = ""
        if g_label:
            try:
                page.get_by_label(re.compile(str(g_label), re.I)).check(force=True)
            except Exception:
                t = page.get_by_text(re.compile(rf"^{re.escape(str(g_label))}$", re.I))
                if t.count():
                    t.first.click()

        ec_raw = (doc.get("estado_civil") or "").upper().strip()
        ec_map = dg.get("estado_civil_map") or {}
        ec = ec_map.get(ec_raw) or ec_map.get(ec_raw.replace("(A)", "")) or ec_raw
        if ec:
            label_ec = dg.get("estado_civil", "Estado Civil")
            sel = page.get_by_label(re.compile(str(label_ec), re.I))
            if sel.count() == 0:
                sel = page.locator("select").filter(has_text=re.compile(r"SOLTERO|CASADO|Civil", re.I))
            if sel.count():
                try:
                    sel.first.select_option(label=re.compile(re.escape(str(ec).split("(")[0]), re.I))
                except Exception:
                    try:
                        sel.first.select_option(label=str(ec))
                    except Exception:
                        log.warning("No se pudo seleccionar estado civil %s", ec)

        fecha = self._normalizar_fecha_dd_mm_aaaa(doc.get("fecha_nacimiento") or "")
        self._fill_if_empty(
            page,
            dg.get("fecha_nacimiento", "Fecha Nacimiento"),
            fecha,
        )
        # Departamento expedido en blanco — no tocar
        # Número Documento / Tipo Documento suelen venir bloqueados

        aceptar = dg.get("boton_aceptar", "^Aceptar$")
        btn = page.get_by_role("button", name=re.compile(str(aceptar), re.I))
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(800)
        else:
            raise RuntimeError("No se encontró botón Aceptar en Datos Generales")

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
        dom = self.selectors.get("domicilio") or {}

        # Paso obligatorio Riberalta: abrir Búsqueda Avanzada para área/tipo/nombre lugar
        ba = dom.get("busqueda_avanzada") or {}
        if ba.get("obligatorio", True):
            name = ba.get("link_name", "Búsqueda Avanzada")
            link = page.get_by_role("link", name=re.compile(str(name), re.I))
            if link.count() == 0:
                link = page.get_by_text(re.compile(str(name), re.I))
            if link.count():
                link.first.click()
                page.wait_for_timeout(900)
                log.info("Abierta Búsqueda Avanzada de domicilio")
                # Completar modal/pantalla de BA (calibración pendiente de capturas)
                self._domicilio_busqueda_avanzada(page, doc)
            else:
                raise RuntimeError("No se encontró link Búsqueda Avanzada en Domicilio Legal")

        # Tras Asociar, distrito/barrio/tipo/nombre ya vienen cargados.
        # Número Puerta: del CI → llenar y NO marcar Sin Número.
        # Si no hay número en el CI → marcar Sin Número (queda S/N).
        # Dirección Descriptiva y Edificio: dejar en blanco.
        puerta = (doc.get("numero_puerta") or "").strip()
        label_puerta = dom.get("numero_puerta", "Número Puerta")
        label_sin = dom.get("sin_numero", "Sin Número")

        if puerta and puerta.upper() not in {"S/N", "SN", "SIN NUMERO", "SIN NÚMERO"}:
            # Desmarcar Sin Número si estuviera marcado
            try:
                sn = page.get_by_label(re.compile(str(label_sin), re.I))
                if sn.count() and sn.first.is_checked():
                    sn.first.uncheck(force=True)
            except Exception:
                pass
            self._fill_if_empty(page, label_puerta, puerta)
            # Forzar fill aunque _fill_if_empty no encuentre label
            try:
                loc = page.get_by_label(re.compile(str(label_puerta), re.I))
                if loc.count():
                    loc.first.fill(puerta)
            except Exception:
                pass
            log.info("Número Puerta desde CI: %s", puerta)
        else:
            try:
                sn = page.get_by_label(re.compile(str(label_sin), re.I))
                if sn.count():
                    if not sn.first.is_checked():
                        sn.first.check(force=True)
                else:
                    page.get_by_text(re.compile(str(label_sin), re.I)).first.click()
            except Exception:
                log.warning("No se pudo marcar Sin Número")
            log.info("Sin número de puerta en CI → marcado Sin Número")

        # No llenar Dirección Descriptiva ni datos de Edificio
        aceptar = dom.get("boton_aceptar", "^Aceptar$")
        btn = page.get_by_role("button", name=re.compile(str(aceptar), re.I))
        if btn.count():
            btn.first.scroll_into_view_if_needed()
            btn.first.click()
            page.wait_for_timeout(800)
        else:
            raise RuntimeError("No se encontró botón Aceptar en Domicilio Legal")

    def _domicilio_busqueda_avanzada(self, page: Page, doc: dict) -> None:
        """
        BUSQUEDA AVANZADA DIRECCION (Riberalta):
        1) URBANO + Tipo=AVENIDA + Nombre=avenida del CI → Buscar
        2) En Resultados: Asociar fila con MISMO barrio Y MISMA avenida del CI
        3) Si no hay esa fila → Nombre=SIN NOMINAR → Buscar → Asociar BARRIO SIN NOMINAR + AVENIDA SIN NOMINAR
        """
        ba = (self.selectors.get("domicilio") or {}).get("busqueda_avanzada_form") or {}
        avenida = (doc.get("avenida") or "").strip()
        barrio = (doc.get("barrio") or "").strip()
        fallback = str(ba.get("fallback_nombre") or "SIN NOMINAR")
        tipo = str(ba.get("tipo_lugar") or "AVENIDA")
        area = str(ba.get("area_default") or "URBANO")
        btn_buscar = str(ba.get("boton_buscar") or "^Buscar$")

        try:
            page.get_by_label(re.compile(area, re.I)).check(force=True)
        except Exception:
            t = page.get_by_text(re.compile(rf"^{re.escape(area)}$", re.I))
            if t.count():
                t.first.click()

        label_tipo = ba.get("label_tipo_lugar", "Tipo Lugar")
        tipo_sel = page.get_by_label(re.compile(str(label_tipo), re.I))
        if tipo_sel.count() == 0:
            tipo_sel = page.locator("select").first
        if tipo_sel.count():
            try:
                tipo_sel.first.select_option(label=re.compile(tipo, re.I))
            except Exception:
                log.warning("No se pudo seleccionar Tipo Lugar=%s", tipo)

        label_nombre = ba.get("label_nombre_lugar", "Nombre Lugar")

        def _set_nombre(valor: str) -> None:
            loc = page.get_by_label(re.compile(str(label_nombre), re.I))
            if loc.count() == 0:
                loc = page.locator("input[type='text']").first
            loc.first.fill(valor)

        def _click_buscar() -> None:
            page.get_by_role("button", name=re.compile(btn_buscar, re.I)).click()
            page.wait_for_timeout(1200)

        if not avenida:
            log.warning("Sin avenida OCR → directo a SIN NOMINAR")
        else:
            _set_nombre(avenida)
            _click_buscar()
            if self._domicilio_asociar_barrio_avenida(page, barrio=barrio, avenida=avenida):
                log.info("Asociado barrio='%s' avenida='%s'", barrio, avenida)
                return
            log.info(
                "No hay fila con barrio='%s' y avenida='%s' → fallback SIN NOMINAR",
                barrio,
                avenida,
            )

        _set_nombre(fallback)
        _click_buscar()
        if self._domicilio_asociar_sin_nominar(page):
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

        rows = page.locator("table").locator("tr").filter(has_text=re.compile(re.escape(avenida), re.I))
        if rows.count() == 0:
            rows = page.locator("tr").filter(has_text=re.compile(re.escape(avenida), re.I))
        if rows.count() == 0:
            return False

        barrio_norm = self._norm_lugar(barrio)
        for i in range(min(rows.count(), 40)):
            row = rows.nth(i)
            text = ""
            try:
                text = row.inner_text()
            except Exception:
                continue
            # Debe contener la avenida; si hay barrio OCR, también debe coincidir
            if avenida.upper() not in text.upper():
                continue
            if barrio_norm and barrio_norm not in self._norm_lugar(text):
                continue
            link = row.get_by_role("link", name=re.compile(asociar_re, re.I))
            if link.count() == 0:
                link = row.get_by_text(re.compile(asociar_re, re.I))
            if link.count():
                link.first.click()
                page.wait_for_timeout(900)
                return True

        # Si no hay barrio OCR, no asociar la primera avenida a ciegas: exigir fallback
        if not barrio_norm:
            log.warning("Hay resultados de avenida pero sin barrio OCR para emparejar")
        return False

    def _domicilio_asociar_sin_nominar(self, page: Page) -> bool:
        ba = (self.selectors.get("domicilio") or {}).get("busqueda_avanzada_form") or {}
        asociar_re = str(ba.get("link_asociar") or "^Asociar$")
        rows = page.locator("tr").filter(has_text=re.compile(r"SIN\s*NOMINAR", re.I))
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
                link.first.click()
                page.wait_for_timeout(900)
                return True
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
        page.wait_for_timeout(500)
        name = self._sel("apoderado", "boton_cancelar", default="^Cancelar$")
        # Si el diálogo nativo ya se cerró, no hay nada que hacer
        if page.get_by_text(re.compile(r"Apoderado|Representante\s*Legal", re.I)).count() == 0:
            log.info("Sin prompt de apoderado visible (posible dismiss nativo ya aplicado)")
            return

        dialog = page.get_by_role("dialog")
        if dialog.count():
            cancelar = dialog.get_by_role("button", name=re.compile(str(name), re.I))
            if cancelar.count():
                cancelar.first.click()
                page.wait_for_timeout(500)
                log.info("Apoderado → Cancelar (HTML dialog)")
                return

        cancelar = page.get_by_role("button", name=re.compile(str(name), re.I))
        if cancelar.count():
            cancelar.last.click()
            page.wait_for_timeout(500)
            log.info("Apoderado → Cancelar (botón)")

    def _info_adicional(self, page: Page, doc: dict) -> None:
        """Solo *Teléfono Celular (aleatorio de la API); resto en blanco → Aceptar."""
        info = self.selectors.get("info_adicional") or {}
        celular = (doc.get("telefono_celular") or "").strip() or "78998541"
        label = info.get("celular", r"Teléfono Celular|Telefono Celular")
        loc = page.get_by_label(re.compile(str(label), re.I))
        if loc.count():
            loc.first.fill(celular)
        else:
            self._fill_if_empty(page, str(label), celular)
        log.info("Celular aleatorio: %s", celular)

        aceptar = info.get("boton_aceptar", "^Aceptar$")
        btn = page.get_by_role("button", name=re.compile(str(aceptar), re.I))
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(700)
        else:
            raise RuntimeError("No se encontró botón Aceptar en Información Adicional")

    def _subir_fotografia(self, page: Page, doc: dict) -> None:
        """Solo sección Fotografía (≤90 KB). No anverso ni reverso."""
        img = self.selectors.get("imagenes") or {}
        foto_cfg = img.get("fotografia") or {}
        url = doc.get("foto_url")
        if not url:
            raise RuntimeError("El documento no trae foto_url — capture la foto en la app")
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

        # Preferir el file input de la fila/sección Fotografía
        idx = int(foto_cfg.get("input_file_index", 0) or 0)
        file_input = None
        seccion = page.locator("tr, div, table").filter(
            has_text=re.compile(r"Fotogra", re.I)
        ).filter(has=page.locator("input[type='file']"))
        if seccion.count():
            file_input = seccion.first.locator("input[type='file']").first
        if file_input is None or file_input.count() == 0:
            css = img.get("input_file", "input[type='file']")
            file_input = page.locator(str(css)).nth(idx)
        if file_input.count() == 0:
            raise RuntimeError("No se encontró input Examinar de Fotografía")

        # Importante: no interactuar con el diálogo Windows «Carga de archivos».
        # set_input_files inyecta la foto del escaneo (foto_url), no una de la carpeta Imágenes.
        file_input.set_input_files(str(dest))
        page.wait_for_timeout(800)
        log.info("Fotografía del escaneo inyectada (sin diálogo Windows): %s", dest.name)

        self._editar_fotografia_procesar(page)

        # Volver a REGISTRAR IMAGENES: bajar y Aceptar (no anverso/reverso)
        page.wait_for_timeout(500)
        aceptar = img.get("boton_aceptar", "^Aceptar$")
        btn = page.get_by_role("button", name=re.compile(str(aceptar), re.I))
        if btn.count() == 0:
            # A veces el botón está fuera de vista / al final del form
            page.keyboard.press("End")
            page.wait_for_timeout(300)
            btn = page.get_by_role("button", name=re.compile(str(aceptar), re.I))
        if btn.count():
            btn.last.scroll_into_view_if_needed()
            btn.last.click()
            page.wait_for_timeout(1000)
            log.info("Registrar Imágenes → Aceptar")
        else:
            raise RuntimeError("No se encontró botón Aceptar al final de Registrar Imágenes")

    def _confirmar_tramite_imprimir(self, page: Page) -> None:
        """
        CONFIRMAR TRAMITE — Pasos Finales:
        1) Imprimir Reporte  ← agente
        2) Grabar            ← NO (modo seguro: operador)
        3) Salir             ← operador
        """
        conf = self.selectors.get("confirmar_tramite") or {}
        page.wait_for_timeout(600)
        titulo = page.get_by_text(re.compile(r"CONFIRMAR\s+TRAMITE", re.I))
        if titulo.count() == 0:
            log.warning("No se vio CONFIRMAR TRAMITE — puede que aún no haya llegado")

        imprimir = page.get_by_role(
            "button",
            name=re.compile(str(conf.get("boton_imprimir", r"^Imprimir\s+Reporte$")), re.I),
        )
        if imprimir.count() == 0:
            imprimir = page.get_by_text(re.compile(r"Imprimir\s+Reporte", re.I))
        if imprimir.count():
            # La impresión puede abrir diálogo del navegador; ya dismissamos confirms de apoderado.
            # Para print, a veces hay que aceptar el diálogo de impresión — dejar que el SO maneje
            # o cancelar el print dialog si aparece.
            try:
                with page.expect_event("popup", timeout=3000) as pop:
                    imprimir.first.click()
                popup = pop.value
                popup.close()
            except Exception:
                imprimir.first.click()
            page.wait_for_timeout(800)
            log.info("CONFIRMAR TRAMITE → Imprimir Reporte (modo seguro: sin Grabar)")
            log.info(
                ">>> OPERADOR: revise el Reporte de Control de Datos, confirme con el contribuyente "
                "y pulse Grabar en RUAT. Luego Salir."
            )
        else:
            raise RuntimeError("No se encontró botón Imprimir Reporte")

        # Explicitamente NO hacer clic en Grabar ni Salir en MVP
        # Fase 2: GRABAR_AUTOMATICO=1 → pulsar Grabar tras Imprimir Reporte
        if os.getenv("GRABAR_AUTOMATICO", "").strip().lower() in {"1", "true", "yes"}:
            grabar = page.get_by_role(
                "button",
                name=re.compile(str(conf.get("boton_grabar", "^Grabar$")), re.I),
            )
            if grabar.count():
                grabar.first.click()
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
        (Ajuste fino del crop por drag queda pendiente si el default falla.)
        """
        edit = (self.selectors.get("imagenes") or {}).get("editar_fotografia") or {}
        page.wait_for_timeout(600)

        # Detectar pantalla de edición
        en_edicion = page.get_by_text(re.compile(r"EDITAR\s+FOTOGRAF", re.I)).count() > 0
        procesar = page.get_by_role("button", name=re.compile(str(edit.get("boton_procesar", "^Procesar$")), re.I))
        if not en_edicion and procesar.count() == 0:
            log.info("No apareció EDITAR FOTOGRAFÍA — se continúa")
            return

        log.info("EDITAR FOTOGRAFÍA: usando cuadro remarcado (default RUAT) → Procesar")
        if procesar.count():
            procesar.first.click()
            page.wait_for_timeout(1200)
        else:
            raise RuntimeError("No se encontró botón Procesar en Editar Fotografía")

        # Tras Procesar aparece panel EDITADO (imagen enmarcada) → Finalizar
        editado = page.get_by_text(re.compile(r"^EDITADO$", re.I))
        if editado.count() == 0:
            page.wait_for_timeout(800)
        finalizar = page.get_by_role(
            "button", name=re.compile(str(edit.get("boton_finalizar", "^Finalizar$")), re.I)
        )
        if finalizar.count():
            finalizar.first.click()
            page.wait_for_timeout(1000)
            log.info("Fotografía enmarcada → Finalizar")
        else:
            raise RuntimeError("No se encontró botón Finalizar tras Procesar la fotografía")

    def _fill_if_empty(self, page: Page, label_pattern: str, value: str) -> None:
        if not value:
            return
        loc = page.get_by_label(re.compile(str(label_pattern), re.I))
        if loc.count() == 0:
            loc = page.locator(f"text=/{label_pattern}/i >> xpath=..//input").first
            if loc.count() == 0:
                log.warning("Campo no encontrado: %s", label_pattern)
                return
            try:
                current = loc.input_value()
            except Exception:
                current = ""
            if not (current or "").strip():
                loc.fill(value)
            return
        try:
            current = loc.first.input_value()
        except Exception:
            current = ""
        if not (current or "").strip():
            loc.first.fill(value)
