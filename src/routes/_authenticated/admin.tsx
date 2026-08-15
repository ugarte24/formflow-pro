import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Download, Loader2, Monitor, Plus, ShieldCheck, Upload, UserPlus, Users } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";
import {
  crearUsuarioApp,
  estadoInstaladorAgente,
  urlDescargaInstaladorAgente,
  type RolUsuario,
} from "@/lib/admin.functions";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({
    meta: [
      { title: "Administración — Digitalizador" },
      {
        name: "description",
        content: "Gestiona computadores, operadores e instalador del agente Windows.",
      },
      { property: "og:title", content: "Administración — Digitalizador" },
      { property: "og:description", content: "Control de PCs, operadores e instalador." },
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
  const [nombre, setNombre] = useState("");
  const [codigo, setCodigo] = useState("");
  const [descargando, setDescargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [creandoUsuario, setCreandoUsuario] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [nuevoPassword, setNuevoPassword] = useState("");
  const [nuevoTelefono, setNuevoTelefono] = useState("");
  const [nuevoRol, setNuevoRol] = useState<RolUsuario>("operador");
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: computadores } = useQuery({
    queryKey: ["computadores"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("computers")
        .select("id, nombre, codigo, activo, last_seen_at")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });

  const { data: operadores } = useQuery({
    queryKey: ["operadores"],
    queryFn: async () => {
      const [{ data: perfiles }, { data: roles }] = await Promise.all([
        supabase
          .from("profiles")
          .select("id, nombre_completo, telefono, activo, created_at")
          .order("created_at"),
        supabase.from("user_roles").select("user_id, role"),
      ]);
      return (perfiles ?? []).map((p) => ({
        ...p,
        activo: p.activo !== false,
        esAdmin: (roles ?? []).some((r) => r.user_id === p.id && r.role === "admin"),
      }));
    },
  });

  const { data: instalador, isLoading: cargandoInstalador } = useQuery({
    queryKey: ["instalador-agente"],
    queryFn: () => estadoInstaladorAgente(),
    enabled: !!sesion?.esAdmin,
  });

  async function crearComputador() {
    if (!nombre.trim() || !codigo.trim()) {
      toast.error("Complete nombre y código del computador");
      return;
    }
    const { error } = await supabase
      .from("computers")
      .insert({ nombre: nombre.trim().slice(0, 80), codigo: codigo.trim().toUpperCase().slice(0, 40) });
    if (error) {
      toast.error(error.message);
      return;
    }
    setNombre("");
    setCodigo("");
    toast.success("Computador autorizado. En el PC del operador use solo el código (sin token).");
    queryClient.invalidateQueries({ queryKey: ["computadores"] });
  }

  async function alternarPcActivo(id: string, activo: boolean) {
    const { error } = await supabase.from("computers").update({ activo: !activo }).eq("id", id);
    if (error) toast.error(error.message);
    else {
      toast.success(!activo ? "PC activado" : "PC desactivado");
      queryClient.invalidateQueries({ queryKey: ["computadores"] });
    }
  }

  async function alternarOperadorActivo(userId: string, activo: boolean) {
    const { error } = await supabase.from("profiles").update({ activo: !activo }).eq("id", userId);
    if (error) toast.error(error.message);
    else {
      toast.success(!activo ? "Operador activado" : "Operador desactivado");
      queryClient.invalidateQueries({ queryKey: ["operadores"] });
    }
  }

  async function alternarAdmin(userId: string, esAdmin: boolean): Promise<void> {
    if (esAdmin) {
      const { error } = await supabase.from("user_roles").delete().eq("user_id", userId).eq("role", "admin");
      if (error) {
        toast.error(error.message);
        return;
      }
    } else {
      const { error } = await supabase.from("user_roles").insert({ user_id: userId, role: "admin" });
      if (error) {
        toast.error(error.message);
        return;
      }
    }
    queryClient.invalidateQueries({ queryKey: ["operadores"] });
  }

  async function crearUsuario() {
    setCreandoUsuario(true);
    try {
      const creado = await crearUsuarioApp({
        data: {
          email: nuevoEmail,
          password: nuevoPassword,
          nombreCompleto: nuevoNombre,
          telefono: nuevoTelefono,
          rol: nuevoRol,
        },
      });
      setNuevoNombre("");
      setNuevoEmail("");
      setNuevoPassword("");
      setNuevoTelefono("");
      setNuevoRol("operador");
      toast.success(
        creado.rol === "admin"
          ? `Administrador creado: ${creado.email}`
          : `Operador creado: ${creado.email}`,
      );
      queryClient.invalidateQueries({ queryKey: ["operadores"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo crear el usuario");
    } finally {
      setCreandoUsuario(false);
    }
  }

  async function descargarInstalador() {
    setDescargando(true);
    try {
      const { url, nombre: fileName } = await urlDescargaInstaladorAgente();
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success("Descarga iniciada. Pasá el ZIP al PC del operador.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo descargar el instalador");
    } finally {
      setDescargando(false);
    }
  }

  async function subirInstalador(file: File) {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      toast.error("Subí el archivo DigitalizadorAgent-Setup.zip");
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      toast.error("El ZIP supera 100 MB");
      return;
    }
    setSubiendo(true);
    try {
      const { error } = await supabase.storage.from("agente").upload("releases/DigitalizadorAgent-Setup.zip", file, {
        upsert: true,
        contentType: "application/zip",
      });
      if (error) throw error;
      toast.success("Instalador publicado. Ya se puede descargar desde Admin.");
      queryClient.invalidateQueries({ queryKey: ["instalador-agente"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo subir el instalador");
    } finally {
      setSubiendo(false);
      if (fileRef.current) fileRef.current.value = "";
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

  return (
    <AppShell titulo="Administración" subtitulo="Computadores, operadores e instalador" esAdmin={sesion?.esAdmin}>
      <section className="panel p-4">
        <p className="label-caps flex items-center gap-1.5">
          <Download className="h-3.5 w-3.5" /> Instalador PC operador
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Descargá el ZIP desde aquí, pasáselo al operador (USB / Drive). Él descomprime, ejecuta{" "}
          <strong>Instalar.bat</strong> y completa solo <strong>CODIGO_PC</strong> (sin token).
        </p>

        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            disabled={descargando || cargandoInstalador || !instalador?.disponible}
            onClick={() => void descargarInstalador()}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          >
            {descargando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Descargar DigitalizadorAgent-Setup.zip
          </button>
          <button
            type="button"
            disabled={subiendo}
            onClick={() => fileRef.current?.click()}
            className="flex items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 text-sm font-medium disabled:opacity-50"
          >
            {subiendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Publicar nueva versión
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void subirInstalador(f);
            }}
          />
        </div>

        <p className="mt-2 text-[11px] text-muted-foreground">
          {cargandoInstalador
            ? "Comprobando instalador…"
            : instalador?.disponible
              ? [
                  "Versión publicada",
                  formatBytes(instalador.bytes),
                  instalador.actualizado
                    ? `actualizada ${new Date(instalador.actualizado).toLocaleString("es-BO")}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ")
              : "Aún no hay instalador. Usá «Publicar nueva versión» con el ZIP generado en desarrollo."}
        </p>
      </section>

      <section className="panel mt-4 p-4">
        <p className="label-caps flex items-center gap-1.5">
          <Monitor className="h-3.5 w-3.5" /> Autorizar computador
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          En el PC del operador solo se configura el <strong>código</strong> (ej. PC-VEN-01). Sin tokens.
        </p>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            maxLength={80}
            placeholder="Nombre (ej. Ventanilla 3)"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.toUpperCase())}
            maxLength={40}
            placeholder="Código único (ej. PC-VEN-03)"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 font-mono text-sm outline-none focus:border-primary"
          />
        </div>
        <button
          onClick={() => void crearComputador()}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
        >
          <Plus className="h-4 w-4" /> Registrar computador
        </button>
      </section>

      <section className="panel mt-4 overflow-hidden">
        <p className="label-caps border-b border-border px-4 py-3">Computadores registrados</p>
        {(computadores ?? []).length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">Sin computadores autorizados.</p>
        ) : (
          <ul className="divide-y divide-border">
            {computadores?.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{c.nombre}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">
                    Código: {c.codigo} ·{" "}
                    {c.last_seen_at
                      ? `visto ${new Date(c.last_seen_at).toLocaleString("es-BO")}`
                      : "nunca conectado"}
                  </p>
                </div>
                <button
                  onClick={() => void alternarPcActivo(c.id, c.activo)}
                  className={`rounded-md px-2 py-1 text-[11px] font-medium ${
                    c.activo ? "bg-success/12 text-success" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {c.activo ? "PC activo" : "PC inactivo"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel mt-4 p-4">
        <p className="label-caps flex items-center gap-1.5">
          <UserPlus className="h-3.5 w-3.5" /> Crear usuario
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Solo quienes tengan usuario creado aquí pueden entrar a la app. Elegí rol{" "}
          <strong>Operador</strong> (escanea y envía) o <strong>Administrador</strong> (también gestiona el sistema).
        </p>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <input
            value={nuevoNombre}
            onChange={(e) => setNuevoNombre(e.target.value)}
            maxLength={120}
            placeholder="Nombre completo"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary sm:col-span-2"
          />
          <input
            value={nuevoEmail}
            onChange={(e) => setNuevoEmail(e.target.value)}
            type="email"
            maxLength={255}
            placeholder="Correo (para iniciar sesión)"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <input
            value={nuevoPassword}
            onChange={(e) => setNuevoPassword(e.target.value)}
            type="password"
            maxLength={72}
            placeholder="Contraseña (mín. 6)"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <input
            value={nuevoTelefono}
            onChange={(e) => setNuevoTelefono(e.target.value)}
            maxLength={40}
            placeholder="Teléfono (opcional)"
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <select
            value={nuevoRol}
            onChange={(e) => setNuevoRol(e.target.value as RolUsuario)}
            className="rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          >
            <option value="operador">Rol: Operador</option>
            <option value="admin">Rol: Administrador</option>
          </select>
        </div>
        <button
          type="button"
          disabled={creandoUsuario}
          onClick={() => void crearUsuario()}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        >
          {creandoUsuario ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
          Crear usuario
        </button>
      </section>

      <section className="panel mt-4 overflow-hidden">
        <p className="label-caps flex items-center gap-1.5 border-b border-border px-4 py-3">
          <Users className="h-3.5 w-3.5" /> Usuarios
        </p>
        <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
          Activá/desactivá el acceso o cambiá el rol. Sin usuario activo no pueden usar el aplicativo.
        </p>
        <ul className="divide-y divide-border">
          {(operadores ?? []).length === 0 ? (
            <li className="px-4 py-8 text-center text-sm text-muted-foreground">
              Todavía no hay usuarios. Creá el primero arriba.
            </li>
          ) : (
            operadores?.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-2 px-4 py-3.5 sm:gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{o.nombre_completo || "Sin nombre"}</p>
                  <p className="text-[11px] text-muted-foreground">{o.telefono || "Sin teléfono"}</p>
                </div>
                <button
                  onClick={() => void alternarOperadorActivo(o.id, o.activo)}
                  className={`rounded-md px-2 py-1 text-[11px] font-medium ${
                    o.activo ? "bg-success/12 text-success" : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {o.activo ? "Activo" : "Desactivado"}
                </button>
                <button
                  onClick={() => void alternarAdmin(o.id, o.esAdmin)}
                  className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium ${
                    o.esAdmin ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                  }`}
                >
                  <ShieldCheck className="h-3.5 w-3.5" /> {o.esAdmin ? "Administrador" : "Operador"}
                </button>
              </li>
            ))
          )}
        </ul>
      </section>
    </AppShell>
  );
}
