import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Camera, ChevronRight, Clock, CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useSesion } from "@/hooks/useSesion";
import { supabase } from "@/integrations/supabase/client";
import { PENDIENTES, TONE_CLASS, statusMetaFor } from "@/lib/document-fields";

export const Route = createFileRoute("/_authenticated/inicio")({
  head: () => ({
    meta: [
      { title: "Inicio del operador — Digitalizador" },
      { name: "description", content: "Escanea documentos, revisa pendientes y consulta lo procesado hoy." },
      { property: "og:title", content: "Inicio del operador — Digitalizador" },
      { property: "og:description", content: "Panel diario del operador de digitalización." },
    ],
  }),
  component: Inicio,
});

function Inicio() {
  const { data: sesion } = useSesion();

  const { data: resumen } = useQuery({
    queryKey: ["resumen", sesion?.userId],
    enabled: !!sesion,
    queryFn: async () => {
      const hoy = new Date();
      hoy.setHours(0, 0, 0, 0);
      const [pendientes, procesados, recientes] = await Promise.all([
        supabase
          .from("documents")
          .select("id", { count: "exact", head: true })
          .in("status", PENDIENTES),
        supabase
          .from("documents")
          .select("id", { count: "exact", head: true })
          .in("status", ["registrado", "formulario_completado"])
          .gte("created_at", hoy.toISOString()),
        supabase
          .from("documents")
          .select("id, numero_documento, nombres, apellidos, status, error_message, created_at")
          .order("created_at", { ascending: false })
          .limit(5),
      ]);
      return {
        pendientes: pendientes.count ?? 0,
        procesados: procesados.count ?? 0,
        recientes: recientes.data ?? [],
      };
    },
  });

  return (
    <AppShell titulo={`Hola, ${sesion?.nombre ?? "Operador"}`} subtitulo="Turno activo" esAdmin={sesion?.esAdmin}>
      <Link
        to="/escanear"
        className="ink-panel flex items-center gap-4 px-5 py-6 transition-transform active:scale-[0.99]"
      >
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Camera className="h-7 w-7" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="label-caps text-primary-foreground/60">Acción principal</span>
          <span className="block text-lg font-semibold">Escanear documento</span>
          <span className="block text-xs text-primary-foreground/70">Captura guiada con verificación previa</span>
        </span>
        <ChevronRight className="h-5 w-5 text-primary-foreground/60" />
      </Link>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Metrica
          icono={<Clock className="h-4 w-4" />}
          label="Pendientes"
          valor={resumen?.pendientes ?? 0}
          nota="Requieren revisión"
        />
        <Metrica
          icono={<CheckCircle2 className="h-4 w-4" />}
          label="Procesados hoy"
          valor={resumen?.procesados ?? 0}
          nota="Enviados y registrados"
        />
      </div>

      <section className="panel mt-4 overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="label-caps">Últimos documentos</p>
          <Link to="/historial" className="text-xs font-medium text-primary">
            Ver historial
          </Link>
        </div>
        {(resumen?.recientes ?? []).length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            Todavía no hay documentos escaneados.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {resumen?.recientes.map((d) => {
              const meta = statusMetaFor(d.status, d.error_message);
              return (
                <li key={d.id}>
                  <Link
                    to="/verificar/$id"
                    params={{ id: d.id }}
                    className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/60"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {d.numero_documento || "Sin número"} · {d.nombres || "—"} {d.apellidos || ""}
                      </p>
                      <p className="font-mono text-[11px] text-muted-foreground">
                        {new Date(d.created_at).toLocaleString("es-BO")}
                      </p>
                    </div>
                    <span className={`rounded-md px-2 py-1 text-[11px] font-medium ${TONE_CLASS[meta.tone]}`}>
                      {meta.label}
                    </span>
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

function Metrica({
  icono,
  label,
  valor,
  nota,
}: {
  icono: React.ReactNode;
  label: string;
  valor: number;
  nota: string;
}) {
  return (
    <div className="panel p-4">
      <span className="flex items-center gap-1.5 text-muted-foreground">{icono}</span>
      <p className="mt-2 font-display text-3xl font-semibold">{valor}</p>
      <p className="text-sm font-medium">{label}</p>
      <p className="text-[11px] text-muted-foreground">{nota}</p>
    </div>
  );
}