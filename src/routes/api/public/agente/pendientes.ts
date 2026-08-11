import { createFileRoute } from "@tanstack/react-router";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

async function autorizar(request: Request) {
  const token = request.headers.get("x-agent-token")?.trim();
  if (!token || token.length < 20) return { error: json({ error: "Token del agente requerido" }, 401) };
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
  const { data: pc } = await supabaseAdmin
    .from("computers")
    .select("id, nombre, codigo, activo")
    .eq("agent_token", token)
    .maybeSingle();
  if (!pc || !pc.activo) return { error: json({ error: "Computador no autorizado" }, 403) };
  await supabaseAdmin.from("computers").update({ last_seen_at: new Date().toISOString() }).eq("id", pc.id);
  return { pc, supabaseAdmin };
}

export const Route = createFileRoute("/api/public/agente/pendientes")({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const auth = await autorizar(request);
        if (auth.error) return auth.error;
        const { pc, supabaseAdmin } = auth;

        const { data, error } = await supabaseAdmin
          .from("documents")
          .select(
            "id, numero_documento, nombres, apellidos, genero, estado_civil, fecha_nacimiento, barrio, avenida, numero_puerta, sent_at",
          )
          .eq("computer_id", pc.id)
          .eq("status", "confirmado")
          .order("sent_at", { ascending: true })
          .limit(5);
        if (error) return json({ error: error.message }, 500);

        if (data && data.length > 0) {
          await supabaseAdmin
            .from("documents")
            .update({ status: "enviado_pc" })
            .in(
              "id",
              data.map((d) => d.id),
            );
        }

        return json({ computador: pc.codigo, documentos: data ?? [] });
      },
    },
  },
});