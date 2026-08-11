import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Mail, Phone, ShieldCheck, Activity } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useSesion } from "@/hooks/useSesion";

export const Route = createFileRoute("/_authenticated/perfil")({
  head: () => ({
    meta: [
      { title: "Mi perfil de operador — Digitalizador" },
      { name: "description", content: "Datos del operador y actividad reciente registrada en el sistema." },
      { property: "og:title", content: "Mi perfil de operador — Digitalizador" },
      { property: "og:description", content: "Consulta tu cuenta y tu actividad de digitalización." },
    ],
  }),
  component: Perfil,
});

function Perfil() {
  const { data: sesion } = useSesion();

  const { data: actividad } = useQuery({
    queryKey: ["actividad", sesion?.userId],
    enabled: !!sesion,
    queryFn: async () => {
      const { data } = await supabase
        .from("operation_logs")
        .select("id, evento, detalle, created_at")
        .eq("operator_id", sesion!.userId)
        .order("created_at", { ascending: false })
        .limit(15);
      return data ?? [];
    },
  });

  return (
    <AppShell titulo="Mi perfil" subtitulo={sesion?.nombre} esAdmin={sesion?.esAdmin}>
      <section className="ink-panel p-5">
        <p className="label-caps text-primary-foreground/60">Operador</p>
        <h2 className="mt-1 font-display text-2xl font-semibold">{sesion?.nombre}</h2>
        <div className="mt-3 space-y-1.5 text-sm text-primary-foreground/80">
          <p className="flex items-center gap-2">
            <Mail className="h-4 w-4" /> {sesion?.email}
          </p>
          <p className="flex items-center gap-2">
            <Phone className="h-4 w-4" /> {sesion?.telefono || "Sin teléfono registrado"}
          </p>
          <p className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" /> {sesion?.esAdmin ? "Administrador" : "Operador"}
          </p>
        </div>
      </section>

      <section className="panel mt-4 overflow-hidden">
        <p className="label-caps flex items-center gap-1.5 border-b border-border px-4 py-3">
          <Activity className="h-3.5 w-3.5" /> Actividad reciente
        </p>
        {(actividad ?? []).length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">Sin actividad registrada.</p>
        ) : (
          <ul className="divide-y divide-border">
            {actividad?.map((a) => (
              <li key={a.id} className="px-4 py-3">
                <p className="text-sm font-medium">{a.evento}</p>
                {a.detalle ? <p className="text-xs text-muted-foreground">{a.detalle}</p> : null}
                <p className="font-mono text-[11px] text-muted-foreground">
                  {new Date(a.created_at).toLocaleString("es-BO")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}