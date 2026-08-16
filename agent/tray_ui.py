"""Bandeja del sistema + diálogos (login / errores) sin consola."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("digitalizador-agent")


def show_error(titulo: str, mensaje: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(titulo, mensaje, parent=root)
        root.destroy()
    except Exception:
        log.error("%s: %s", titulo, mensaje)


def show_info(titulo: str, mensaje: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(titulo, mensaje, parent=root)
        root.destroy()
    except Exception:
        log.info("%s: %s", titulo, mensaje)


def prompt_credentials(titulo: str = "Digitalizador Agent") -> tuple[str, str] | None:
    """Diálogo email + contraseña. None si cancela."""
    import tkinter as tk
    from tkinter import ttk

    result: dict[str, str | None] = {"email": None, "password": None}

    root = tk.Tk()
    root.title(titulo)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frm = ttk.Frame(root, padding=16)
    frm.grid(row=0, column=0)

    ttk.Label(frm, text="Inicie sesión con la misma cuenta de la web").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )
    ttk.Label(frm, text="Email").grid(row=1, column=0, sticky="w")
    email_var = tk.StringVar()
    email_entry = ttk.Entry(frm, textvariable=email_var, width=36)
    email_entry.grid(row=1, column=1, pady=4)

    ttk.Label(frm, text="Contraseña").grid(row=2, column=0, sticky="w")
    pass_var = tk.StringVar()
    pass_entry = ttk.Entry(frm, textvariable=pass_var, show="*", width=36)
    pass_entry.grid(row=2, column=1, pady=4)

    err = ttk.Label(frm, text="", foreground="#b00020")
    err.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 8))

    def aceptar() -> None:
        email = email_var.get().strip()
        password = pass_var.get()
        if not email or not password:
            err.configure(text="Email y contraseña son obligatorios")
            return
        result["email"] = email
        result["password"] = password
        root.destroy()

    def cancelar() -> None:
        root.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=2, sticky="e")
    ttk.Button(btns, text="Cancelar", command=cancelar).pack(side="right", padx=(8, 0))
    ttk.Button(btns, text="Entrar", command=aceptar).pack(side="right")

    root.bind("<Return>", lambda _e: aceptar())
    root.bind("<Escape>", lambda _e: cancelar())
    email_entry.focus_set()

    # Centrar
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{x}+{y}")

    root.mainloop()

    if result["email"] and result["password"]:
        return str(result["email"]), str(result["password"])
    return None


def _load_icon_image(ico_path: Path | None):
    from PIL import Image

    if ico_path and ico_path.exists():
        try:
            img = Image.open(ico_path)
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            return img.convert("RGBA").resize((64, 64))
        except Exception as exc:
            log.warning("No se pudo cargar icono %s: %s", ico_path, exc)

    # Fallback: círculo azul simple
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(30, 90, 180, 255))
    return img


class TrayApp:
    """Icono en la bandeja; el ciclo de trabajo corre en un hilo aparte."""

    def __init__(
        self,
        *,
        title: str,
        status_fn: Callable[[], str],
        user_label: str,
        log_path: Path,
        app_dir: Path,
        ico_path: Path | None,
        on_quit: Callable[[], None],
        on_logout: Callable[[], None] | None = None,
        on_show: Callable | None = None,
        on_update: Callable | None = None,
    ) -> None:
        self.title = title
        self.status_fn = status_fn
        self.user_label = user_label
        self.log_path = log_path
        self.app_dir = app_dir
        self.ico_path = ico_path
        self.on_quit = on_quit
        self.on_logout = on_logout
        self.on_show = on_show
        self.on_update = on_update
        self._icon = None
        self._stop = threading.Event()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        self._stop.set()
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _open_log(self, _icon=None, _item=None) -> None:
        try:
            if self.log_path.exists():
                os.startfile(self.log_path)  # type: ignore[attr-defined]
            else:
                show_info("Digitalizador Agent", "Todavía no hay archivo de log.")
        except Exception as exc:
            show_error("Digitalizador Agent", f"No se pudo abrir el log:\n{exc}")

    def _open_folder(self, _icon=None, _item=None) -> None:
        try:
            os.startfile(self.app_dir)  # type: ignore[attr-defined]
        except Exception as exc:
            show_error("Digitalizador Agent", f"No se pudo abrir la carpeta:\n{exc}")

    def _do_quit(self, _icon=None, _item=None) -> None:
        self._stop.set()
        try:
            self.on_quit()
        finally:
            if self._icon is not None:
                self._icon.stop()

    def _do_logout(self, _icon=None, _item=None) -> None:
        if self.on_logout:
            self.on_logout()
        self._do_quit()

    def run(self) -> None:
        import pystray
        from pystray import MenuItem as Item

        image = _load_icon_image(self.ico_path)

        def status_text(_item=None) -> str:
            try:
                return f"Estado: {self.status_fn()}"
            except Exception:
                return "Estado: —"

        items = []
        if self.on_show:
            items.append(Item("Mostrar ventana", self.on_show))
        items.append(Item(lambda item: status_text(item), None, enabled=False))
        items.append(Item(f"Usuario: {self.user_label}", None, enabled=False))
        if self.on_update:
            items.append(Item("Actualizar", self.on_update))
        items.append(Item("Ver log", self._open_log))
        items.append(Item("Abrir carpeta del agente", self._open_folder))
        items.append(pystray.Menu.SEPARATOR)
        if self.on_logout:
            items.append(Item("Cerrar sesión y salir", self._do_logout))
        items.append(Item("Salir", self._do_quit))
        menu = pystray.Menu(*items)

        self._icon = pystray.Icon("digitalizador-agent", image, self.title, menu)
        # Bloquea hasta stop()
        self._icon.run()
