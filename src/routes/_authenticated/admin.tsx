import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { KeyRound, Monitor, Plus, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";
import { obtenerTokenAgente, rotarTokenAgente } from "@/lib/admin.functions";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({
    meta: [
      { title: "Administración — Digitalizador" },
      { name: "description", content: "Gestiona computadores autorizados, tokens del agente y roles de operadores." },
      { property: "og:title", content: "Administración — Digitalizador" },
      { property: "og:description", content: "Control de PCs autorizados y operadores del sistema." },
    ],
  }),
  component: Admin,
});

function Admin() {
  const { data: sesion } = useSesion();
  const queryClient = useQueryClient();
  const verToken = useServerFn(obtenerTokenAgente);
  const rotarToken = useServerFn(rotarTokenAgente);
  const [nombre, setNombre] = useState("");
  const [codigo, setCodigo] = useState("");
  const [tokens, setTokens] = useState<Record<string, string>>({});

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
        supabase.from("profiles").select("id, nombre_completo, telefono, created_at").order("created_at"),
        supabase.from("user_roles").select("user_id, role"),
      ]);
      return (perfiles ?? []).map((p) => ({
        ...p,
        esAdmin: (roles ?? []).some((r) => r.user_id === p.id && r.role === "admin"),
      }));
    },
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
    toast.success("Computador autorizado");
    queryClient.invalidateQueries({ queryKey: ["computadores"] });
  }

  async function alternarActivo(id: string, activo: boolean) {
    const { error } = await supabase.from("computers").update({ activo: !activo }).eq("id", id);
    if (error) toast.error(error.message);
    else queryClient.invalidateQueries({ queryKey: ["computadores"] });
  }

  async function alternarAdmin(userId: string, esAdmin: boolean): Promise<void> {
    if (esAdmin) {
      const { error } = await supabase.from("user_roles").delete().eq("user_id", userId).eq("role", "admin");
      if (error) return toast.error(error.message);
    } else {
      const { error } = await supabase.from("user_roles").insert({ user_id: userId, role: "admin" });
      if (error) return toast.error(error.message);
    }
    queryClient.invalidateQueries({ queryKey: ["operadores"] });
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
    <AppShell titulo="Administración" subtitulo="Computadores y operadores" esAdmin={sesion?.esAdmin}>
      <section className="panel p-4">
        <p className="label-caps flex items-center gap-1.5">
          <Monitor className="h-3.5 w-3.5" /> Autorizar computador
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
              <li key={c.id} className="px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{c.nombre}</p>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {c.codigo} ·{" "}
                      {c.last_seen_at
                        ? `visto ${new Date(c.last_seen_at).toLocaleString("es-BO")}`
                        : "nunca conectado"}
                    </p>
                  </div>
                  <button
                    onClick={() => void alternarActivo(c.id, c.activo)}
                    className={`rounded-md px-2 py-1 text-[11px] font-medium ${
                      c.activo ? "bg-success/12 text-success" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {c.activo ? "Activo" : "Inactivo"}
                  </button>
                </div>
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <button
                    onClick={async () => {
                      try {
                        const r = await verToken({ data: { computerId: c.id } });
                        setTokens((t) => ({ ...t, [c.id]: r.token }));
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : "No se pudo obtener el token");
                      }
                    }}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium"
                  >
                    <KeyRound className="h-3.5 w-3.5" /> Ver token del agente
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const r = await rotarToken({ data: { computerId: c.id } });
                        setTokens((t) => ({ ...t, [c.id]: r.token }));
                        toast.success("Token rotado");
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : "No se pudo rotar el token");
                      }
                    }}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Rotar
                  </button>
                  {tokens[c.id] ? (
                    <code className="w-full break-all rounded-lg bg-muted px-2.5 py-2 font-mono text-[11px]">
                      {tokens[c.id]}
                    </code>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel mt-4 overflow-hidden">
        <p className="label-caps flex items-center gap-1.5 border-b border-border px-4 py-3">
          <Users className="h-3.5 w-3.5" /> Operadores
        </p>
        <ul className="divide-y divide-border">
          {operadores?.map((o) => (
            <li key={o.id} className="flex items-center gap-3 px-4 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{o.nombre_completo || "Sin nombre"}</p>
                <p className="text-[11px] text-muted-foreground">{o.telefono || "Sin teléfono"}</p>
              </div>
              <button
                onClick={() => void alternarAdmin(o.id, o.esAdmin)}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium ${
                  o.esAdmin ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                }`}
              >
                <ShieldCheck className="h-3.5 w-3.5" /> {o.esAdmin ? "Administrador" : "Operador"}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  );
}