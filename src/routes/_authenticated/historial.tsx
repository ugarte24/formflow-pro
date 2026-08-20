import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Search, ChevronRight } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";
import { EN_CURSO, PENDIENTES, TONE_CLASS, statusMetaFor } from "@/lib/document-fields";

export const Route = createFileRoute("/_authenticated/historial")({
  head: () => ({
    meta: [
      { title: "Historial de documentos — Digitalizador" },
      { name: "description", content: "Consulta el estado de cada documento escaneado, enviado y registrado." },
      { property: "og:title", content: "Historial de documentos — Digitalizador" },
      { property: "og:description", content: "Trazabilidad completa de los registros procesados." },
    ],
  }),
  component: Historial,
});

const FILTROS = [
  { key: "todos", label: "Todos" },
  { key: "pendientes", label: "Pendientes" },
  { key: "en_curso", label: "En curso" },
  { key: "registrado", label: "Registrados" },
] as const;

function Historial() {
  const { data: sesion } = useSesion();
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]["key"]>("todos");
  const [busqueda, setBusqueda] = useState("");

  const { data: documentos } = useQuery({
    queryKey: ["historial", filtro],
    queryFn: async () => {
      let q = supabase
        .from("documents")
        .select("id, numero_documento, nombres, apellidos, status, error_message, created_at")
        .order("created_at", { ascending: false })
        .limit(100);
      if (filtro === "pendientes") q = q.in("status", PENDIENTES);
      if (filtro === "en_curso") q = q.in("status", EN_CURSO);
      if (filtro === "registrado") q = q.eq("status", "registrado");
      const { data, error } = await q;
      if (error) throw error;
      return data;
    },
  });

  const termino = busqueda.trim().toLowerCase();
  const lista = (documentos ?? []).filter((d) =>
    termino
      ? `${d.numero_documento ?? ""} ${d.nombres ?? ""} ${d.apellidos ?? ""}`.toLowerCase().includes(termino)
      : true,
  );

  return (
    <AppShell titulo="Historial" subtitulo="Últimos 100 documentos" esAdmin={sesion?.esAdmin}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          maxLength={60}
          placeholder="Buscar por documento o nombre"
          className="w-full rounded-xl border border-input bg-card py-3 pl-10 pr-3.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-ring/25"
        />
      </div>

      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
        {FILTROS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFiltro(f.key)}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              filtro === f.key
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card text-muted-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <section className="panel mt-3 overflow-hidden">
        {lista.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">No hay documentos para este filtro.</p>
        ) : (
          <ul className="divide-y divide-border">
            {lista.map((d) => {
              const meta = statusMetaFor(d.status, d.error_message);
              return (
                <li key={d.id}>
                  <Link
                    to="/verificar/$id"
                    params={{ id: d.id }}
                    className="flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-muted/60"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {d.nombres || "Sin nombre"} {d.apellidos || ""}
                      </p>
                      <p className="font-mono text-[11px] text-muted-foreground">
                        {d.numero_documento || "—"} · {new Date(d.created_at).toLocaleString("es-BO")}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-md px-2 py-1 text-[11px] font-medium ${TONE_CLASS[meta.tone]}`}>
                      {meta.label}
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </AppShell>
  );
}