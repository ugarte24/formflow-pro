import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Download, Loader2, Pencil, ShieldCheck, UserPlus, Users } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";
import {
  crearUsuarioApp,
  editarUsuarioApp,
  estadoInstaladorAgente,
  listarUsuariosApp,
  urlDescargaInstaladorAgente,
  type RolUsuario,
  type UsuarioAdmin,
} from "@/lib/admin.functions";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({
    meta: [
      { title: "Administración — Digitalizador" },
      {
        name: "description",
        content: "Gestiona usuarios e instalador del agente Windows.",
      },
      { property: "og:title", content: "Administración — Digitalizador" },
      { property: "og:description", content: "Usuarios e instalador del sistema." },
    ],
  }),
  component: Admin,
});

function formatBytes(n: number | null | undefined) {
  if (n == null || !Number.isFinite(n)) return "";
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function Admin() {
  const { data: sesion } = useSesion();
  const queryClient = useQueryClient();
  const [descargando, setDescargando] = useState(false);
  const [guardandoUsuario, setGuardandoUsuario] = useState(false);
  const [modalUsuario, setModalUsuario] = useState(false);
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [nuevoPassword, setNuevoPassword] = useState("");
  const [nuevoTelefono, setNuevoTelefono] = useState("");
  const [nuevoRol, setNuevoRol] = useState<RolUsuario>("operador");

  const { data: operadores } = useQuery({
    queryKey: ["operadores"],
    queryFn: () => listarUsuariosApp(),
    enabled: !!sesion?.esAdmin,
  });

  const { data: instalador, isLoading: cargandoInstalador } = useQuery({
    queryKey: ["instalador-agente"],
    queryFn: () => estadoInstaladorAgente(),
    enabled: !!sesion?.esAdmin,
  });

  async function alternarOperadorActivo(userId: string, activo: boolean) {
    const { error } = await supabase.from("profiles").update({ activo: !activo }).eq("id", userId);
    if (error) toast.error(error.message);
    else {
      toast.success(!activo ? "Usuario activado" : "Usuario desactivado");
      queryClient.invalidateQueries({ queryKey: ["operadores"] });
    }
  }

  function resetFormUsuario() {
    setEditandoId(null);
    setNuevoNombre("");
    setNuevoEmail("");
    setNuevoPassword("");
    setNuevoTelefono("");
    setNuevoRol("operador");
  }

  function abrirCrear() {
    resetFormUsuario();
    setModalUsuario(true);
  }

  function abrirEditar(u: UsuarioAdmin) {
    setEditandoId(u.id);
    setNuevoNombre(u.nombre_completo ?? "");
    setNuevoEmail(u.email ?? "");
    setNuevoPassword("");
    setNuevoTelefono(u.telefono ?? "");
    setNuevoRol(u.esAdmin ? "admin" : "operador");
    setModalUsuario(true);
  }

  // Autofill solo molesta al crear; en edición no vaciar.
  useEffect(() => {
    if (!modalUsuario || editandoId) return;
    const t = window.setTimeout(() => {
      setNuevoNombre("");
      setNuevoEmail("");
      setNuevoPassword("");
      setNuevoTelefono("");
      setNuevoRol("operador");
    }, 50);
    return () => window.clearTimeout(t);
  }, [modalUsuario, editandoId]);

  async function guardarUsuario() {
    setGuardandoUsuario(true);
    try {
      if (editandoId) {
        const actualizado = await editarUsuarioApp({
          data: {
            userId: editandoId,
            email: nuevoEmail,
            password: nuevoPassword || undefined,
            nombreCompleto: nuevoNombre,
            telefono: nuevoTelefono,
            rol: nuevoRol,
          },
        });
        toast.success(`Usuario actualizado: ${actualizado.email}`);
      } else {
        const creado = await crearUsuarioApp({
          data: {
            email: nuevoEmail,
            password: nuevoPassword,
            nombreCompleto: nuevoNombre,
            telefono: nuevoTelefono,
            rol: nuevoRol,
          },
        });
        toast.success(
          creado.rol === "admin"
            ? `Administrador creado: ${creado.email}`
            : `Operador creado: ${creado.email}`,
        );
      }
      resetFormUsuario();
      setModalUsuario(false);
      queryClient.invalidateQueries({ queryKey: ["operadores"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo guardar el usuario");
    } finally {
      setGuardandoUsuario(false);
    }
  }

  async function descargarInstalador() {
    setDescargando(true);
    try {
      const { url, nombre: fileName } = await urlDescargaInstaladorAgente();
      const res = await fetch(url);
      if (!res.ok) throw new Error("No se pudo obtener el instalador");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success(`Descarga: ${fileName}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo descargar el instalador");
    } finally {
      setDescargando(false);
    }
  }

  if (sesion && !sesion.esAdmin) {
    return (
      <AppShell titulo="Administración" esAdmin={false}>
        <div className="panel p-6 text-center text-sm text-muted-foreground">
          Esta sección está reservada para administradores.
        </div>
      </AppShell>
    );
  }

  const versionLabel = instalador?.disponible
    ? instalador.version
      ? `v${instalador.version}`
      : "versión sin número"
    : null;

  const esEdicion = !!editandoId;

  return (
    <AppShell titulo="Administración" subtitulo="Usuarios e instalador" esAdmin={sesion?.esAdmin}>
      <section className="panel p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="label-caps flex items-center gap-1.5">
            <Download className="h-3.5 w-3.5" /> Instalador PC operador
          </p>
          {versionLabel ? (
            <span className="rounded-md bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-primary">
              {versionLabel}
            </span>
          ) : null}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Descargá la última versión y pasásela al operador. Él descomprime y ejecuta{" "}
          <strong>Instalar.bat</strong> — no tiene que configurar códigos.
        </p>

        <button
          type="button"
          disabled={descargando || cargandoInstalador || !instalador?.disponible}
          onClick={() => void descargarInstalador()}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        >
          {descargando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {instalador?.disponible && instalador.version
            ? `Descargar instalador v${instalador.version}`
            : "Descargar instalador"}
        </button>

        <p className="mt-2 text-[11px] text-muted-foreground">
          {cargandoInstalador
            ? "Comprobando instalador…"
            : instalador?.disponible
              ? [
                  versionLabel,
                  formatBytes(instalador.bytes),
                  instalador.actualizado
                    ? `publicada ${new Date(instalador.actualizado).toLocaleString("es-BO")}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ")
              : "Todavía no hay instalador publicado."}
        </p>
      </section>

      <section className="panel mt-4 overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <p className="label-caps flex items-center gap-1.5">
            <Users className="h-3.5 w-3.5" /> Usuarios
          </p>
          <button
            type="button"
            onClick={abrirCrear}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-[11px] font-semibold text-primary-foreground"
          >
            <UserPlus className="h-3.5 w-3.5" /> Crear usuario
          </button>
        </div>
        <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
          Creá o editá usuarios. Activá/desactivá el acceso cuando haga falta.
        </p>
        <ul className="divide-y divide-border">
          {(operadores ?? []).length === 0 ? (
            <li className="px-4 py-8 text-center text-sm text-muted-foreground">
              Todavía no hay usuarios. Pulsá «Crear usuario».
            </li>
          ) : (
            operadores?.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-2 px-4 py-3.5 sm:gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{o.nombre_completo || "Sin nombre"}</p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {o.email || "Sin correo"}
                    {o.telefono ? ` · ${o.telefono}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => abrirEditar(o)}
                  className="flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-[11px] font-medium text-foreground"
                >
                  <Pencil className="h-3.5 w-3.5" /> Editar
                </button>
                <button
                  type="button"
                  onClick={() => void alternarOperadorActivo(o.id, o.activo)}
                  className={`rounded-md px-2 py-1 text-[11px] font-medium ${
                    o.activo ? "bg-success/12 text-success" : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {o.activo ? "Activo" : "Desactivado"}
                </button>
                <span
                  className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium ${
                    o.esAdmin ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                  }`}
                >
                  <ShieldCheck className="h-3.5 w-3.5" /> {o.esAdmin ? "Administrador" : "Operador"}
                </span>
              </li>
            ))
          )}
        </ul>
      </section>

      <Dialog
        open={modalUsuario}
        onOpenChange={(open) => {
          if (guardandoUsuario) return;
          setModalUsuario(open);
          if (!open) resetFormUsuario();
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{esEdicion ? "Editar usuario" : "Crear usuario"}</DialogTitle>
            <DialogDescription>
              {esEdicion
                ? "Actualizá los datos. Dejá la contraseña en blanco si no querés cambiarla."
                : "Elegí rol Operador (escanea y envía) o Administrador (también gestiona el sistema)."}
            </DialogDescription>
          </DialogHeader>

          <div
            aria-hidden
            className="pointer-events-none absolute -left-[9999px] h-0 w-0 overflow-hidden opacity-0"
          >
            <input type="text" name="username" tabIndex={-1} autoComplete="username" />
            <input type="password" name="password" tabIndex={-1} autoComplete="current-password" />
          </div>

          <form
            className="grid gap-2.5"
            autoComplete="off"
            onSubmit={(e) => {
              e.preventDefault();
              void guardarUsuario();
            }}
          >
            <input
              value={nuevoNombre}
              onChange={(e) => setNuevoNombre(e.target.value)}
              name="ff-nombre-nuevo"
              autoComplete="off"
              maxLength={120}
              placeholder="Nombre completo"
              className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
            />
            <input
              value={nuevoEmail}
              onChange={(e) => setNuevoEmail(e.target.value)}
              type="email"
              name="ff-correo-nuevo"
              autoComplete="off"
              maxLength={255}
              placeholder="Correo (para iniciar sesión)"
              className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
            />
            <input
              value={nuevoPassword}
              onChange={(e) => setNuevoPassword(e.target.value)}
              type="password"
              name="ff-clave-nueva"
              autoComplete="new-password"
              maxLength={72}
              placeholder={esEdicion ? "Nueva contraseña (opcional)" : "Contraseña (mín. 6)"}
              className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
            />
            <input
              value={nuevoTelefono}
              onChange={(e) => setNuevoTelefono(e.target.value)}
              name="ff-telefono-nuevo"
              autoComplete="off"
              maxLength={40}
              placeholder="Teléfono (opcional)"
              className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
            />
            <select
              value={nuevoRol}
              onChange={(e) => setNuevoRol(e.target.value as RolUsuario)}
              name="ff-rol-nuevo"
              autoComplete="off"
              className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
            >
              <option value="operador">Rol: Operador</option>
              <option value="admin">Rol: Administrador</option>
            </select>
          </form>

          <DialogFooter className="gap-2 sm:gap-0">
            <button
              type="button"
              disabled={guardandoUsuario}
              onClick={() => setModalUsuario(false)}
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-medium"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={guardandoUsuario}
              onClick={() => void guardarUsuario()}
              className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {guardandoUsuario ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : esEdicion ? (
                <Pencil className="h-4 w-4" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              {esEdicion ? "Guardar" : "Crear"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
