"""Ventana principal del agente + bandeja."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from tray_ui import TrayApp, show_error
from updater import check_and_update, fetch_update_info, is_newer, local_version

log = logging.getLogger("digitalizador-agent")


class AgentWindow:
    def __init__(
        self,
        *,
        base_url: str,
        user_label: str,
        status_fn: Callable[[], str],
        log_path,
        app_dir,
        ico_path,
        on_quit: Callable[[], None],
        on_logout: Callable[[], None] | None = None,
        on_iniciar: Callable[[], None] | None = None,
        on_pausar: Callable[[], None] | None = None,
    ) -> None:
        self.base_url = base_url
        self.user_label = user_label
        self.status_fn = status_fn
        self.log_path = log_path
        self.app_dir = app_dir
        self.ico_path = ico_path
        self.on_quit = on_quit
        self.on_logout = on_logout
        self.on_iniciar = on_iniciar
        self.on_pausar = on_pausar
        self.version = local_version()
        self._updating = False
        self._closed = False

        self.root = tk.Tk()
        self.root.title("Digitalizador Agent")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)

        try:
            if ico_path and ico_path.exists():
                self.root.iconbitmap(default=str(ico_path))
        except Exception:
            pass

        pad = ttk.Frame(self.root, padding=18)
        pad.grid(row=0, column=0, sticky="nsew")

        ttk.Label(pad, text="Digitalizador Agent", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            pad,
            text="Usted abre RUAT e inicia sesión; luego pulse Iniciar",
            foreground="#666",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.lbl_user = ttk.Label(pad, text=f"Usuario: {user_label}")
        self.lbl_user.grid(row=2, column=0, columnspan=2, sticky="w")

        self.lbl_ver = ttk.Label(pad, text=f"Versión: v{self.version}")
        self.lbl_ver.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.lbl_status = ttk.Label(pad, text="Estado: —", wraplength=360)
        self.lbl_status.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 4))

        self.lbl_update = ttk.Label(pad, text="", foreground="#0b57d0", wraplength=360)
        self.lbl_update.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 10))

        btns = ttk.Frame(pad)
        btns.grid(row=6, column=0, columnspan=2, sticky="ew")

        if on_iniciar:
            self.btn_iniciar = ttk.Button(btns, text="Iniciar", command=self._click_iniciar)
            self.btn_iniciar.pack(side="left")
        if on_pausar:
            ttk.Button(btns, text="Pausar", command=self._click_pausar).pack(side="left", padx=(8, 0))

        self.btn_update = ttk.Button(btns, text="Actualizar", command=self._click_update)
        self.btn_update.pack(side="left", padx=(8, 0))

        ttk.Button(btns, text="Ver log", command=self._open_log).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Minimizar", command=self._minimize_to_tray).pack(side="left", padx=(8, 0))

        bottom = ttk.Frame(pad)
        bottom.grid(row=7, column=0, columnspan=2, sticky="e", pady=(14, 0))
        if on_logout:
            ttk.Button(bottom, text="Cerrar sesión", command=self._logout).pack(side="right", padx=(8, 0))
        ttk.Button(bottom, text="Salir", command=self._quit).pack(side="right")

        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 4
        self.root.geometry(f"+{x}+{y}")

        self.tray = TrayApp(
            title="Digitalizador Agent",
            status_fn=status_fn,
            user_label=user_label,
            log_path=log_path,
            app_dir=app_dir,
            ico_path=ico_path,
            on_quit=self._quit_from_tray,
            on_logout=self._logout_from_tray if on_logout else None,
            on_show=self._show_from_tray,
            on_update=self._click_update,
            on_iniciar=self._click_iniciar if on_iniciar else None,
            on_pausar=self._click_pausar if on_pausar else None,
        )
        self._tray_thread = threading.Thread(target=self.tray.run, name="tray", daemon=True)
        self._tray_thread.start()

        self.root.after(400, self._tick)
        self.root.after(800, self._silent_check_update_label)

    def _click_iniciar(self, _icon=None, _item=None) -> None:
        if self.on_iniciar:
            self.on_iniciar()

    def _click_pausar(self, _icon=None, _item=None) -> None:
        if self.on_pausar:
            self.on_pausar()

    def run(self) -> None:
        self.root.mainloop()

    def _tick(self) -> None:
        if self._closed:
            return
        try:
            self.lbl_status.configure(text=f"Estado: {self.status_fn()}")
        except Exception:
            pass
        self.root.after(1000, self._tick)

    def _silent_check_update_label(self) -> None:
        def work() -> None:
            info = fetch_update_info(self.base_url)
            if not info:
                return
            remote = str(info["version"])
            if is_newer(remote, self.version):

                def ui() -> None:
                    self.lbl_update.configure(text=f"Nueva versión disponible: v{remote}")
                    self.btn_update.configure(text=f"Actualizar a v{remote}")

                self.root.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def _set_update_msg(self, msg: str) -> None:
        self.lbl_update.configure(text=msg)

    def _click_update(self, _icon=None, _item=None) -> None:
        if self._updating:
            return
        self._updating = True
        self.btn_update.configure(state="disabled")
        self._set_update_msg("Buscando actualizaciones…")

        def work() -> None:
            try:
                def progress(msg: str) -> None:
                    self.root.after(0, lambda m=msg: self._set_update_msg(m))

                def ask(title: str, body: str) -> bool:
                    result: dict[str, bool] = {"ok": False}
                    ev = threading.Event()

                    def dlg() -> None:
                        result["ok"] = bool(messagebox.askyesno(title, body, parent=self.root))
                        ev.set()

                    self.root.after(0, dlg)
                    ev.wait(timeout=300)
                    return result["ok"]

                started = check_and_update(
                    self.base_url,
                    auto=False,
                    progress=progress,
                    ask=ask,
                )
                if started:
                    self.root.after(0, self._quit_for_update)
                    return

                info = fetch_update_info(self.base_url)
                if info and not is_newer(str(info["version"]), self.version):
                    self.root.after(
                        0,
                        lambda: (
                            self._set_update_msg(f"Ya está actualizado (v{self.version})"),
                            self.btn_update.configure(state="normal"),
                        ),
                    )
                else:
                    self.root.after(
                        0,
                        lambda: (
                            self._set_update_msg("No se pudo actualizar. Revise el log."),
                            self.btn_update.configure(state="normal"),
                        ),
                    )
            except Exception as exc:
                log.exception("Error al actualizar")
                self.root.after(
                    0,
                    lambda: (
                        self._set_update_msg(str(exc)),
                        self.btn_update.configure(state="normal"),
                        show_error("Actualización", str(exc)),
                    ),
                )
            finally:
                self._updating = False

        threading.Thread(target=work, daemon=True).start()

    def _quit_for_update(self) -> None:
        """Salida inmediata tras lanzar el updater (no esperar Playwright/worker)."""
        self._set_update_msg("Instalando y reiniciando…")
        try:
            self.on_quit()
        except Exception:
            pass
        try:
            self.tray.request_stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _open_log(self) -> None:
        try:
            if self.log_path.exists():
                os.startfile(self.log_path)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Digitalizador Agent", "Todavía no hay archivo de log.", parent=self.root)
        except Exception as exc:
            show_error("Digitalizador Agent", str(exc))

    def _minimize_to_tray(self) -> None:
        self.root.withdraw()

    def _show_from_tray(self, _icon=None, _item=None) -> None:
        def show() -> None:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()

        self.root.after(0, show)

    def _logout(self) -> None:
        if self.on_logout:
            self.on_logout()
        self._quit()

    def _logout_from_tray(self, _icon=None, _item=None) -> None:
        self.root.after(0, self._logout)

    def _quit_from_tray(self, _icon=None, _item=None) -> None:
        self.root.after(0, self._quit)

    def _quit(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.on_quit()
        except Exception:
            pass
        try:
            self.tray.request_stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def run_startup_update(base_url: str) -> bool:
    """
    Al iniciar: si hay versión nueva, actualiza en silencio (con ventana de progreso).
    Devuelve True si hay que salir para reiniciar.
    """
    from updater import check_and_update, fetch_update_info, is_newer, local_version
    from app_paths import is_frozen

    if not is_frozen():
        return False

    info = fetch_update_info(base_url)
    if not info or not is_newer(str(info["version"]), local_version()):
        return False

    remote = str(info["version"])
    root = tk.Tk()
    root.title("Digitalizador Agent — Actualización")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frm = ttk.Frame(root, padding=20)
    frm.pack()
    ttk.Label(frm, text=f"Actualizando a v{remote}…", font=("Segoe UI", 11, "bold")).pack(anchor="w")
    lbl = ttk.Label(frm, text="Preparando…", wraplength=360)
    lbl.pack(anchor="w", pady=(8, 0))
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{x}+{y}")

    result: dict[str, bool] = {"ok": False}
    err: dict[str, str] = {"msg": ""}

    def progress(msg: str) -> None:
        def ui() -> None:
            lbl.configure(text=msg)
            root.update_idletasks()

        root.after(0, ui)

    def work() -> None:
        try:
            result["ok"] = check_and_update(base_url, auto=True, progress=progress)
        except Exception as exc:
            err["msg"] = str(exc)
            log.exception("Fallo actualización al inicio")
        finally:
            root.after(0, root.destroy)

    threading.Thread(target=work, daemon=True).start()
    root.mainloop()

    if err["msg"]:
        show_error(
            "Digitalizador Agent",
            f"No se pudo actualizar automáticamente:\n{err['msg']}\n\n"
            "Se continuará con la versión actual.\n\n"
            "Si se repite: Admin → Descargar agente → Instalar.bat "
            "(cierre el agente antes).",
        )
        return False
    return result["ok"]
