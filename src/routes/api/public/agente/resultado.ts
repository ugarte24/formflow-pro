import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

const Esquema = z.object({
  documentId: z.string().uuid(),
  estado: z.enum(["formulario_completado", "registrado", "error_automatizacion", "error_sistema"]),
  mensaje: z.string().max(500).optional(),
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

export const Route = createFileRoute("/api/public/agente/resultado")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const token = request.headers.get("x-agent-token")?.trim();
        if (!token || token.length < 20) return json({ error: "Token del agente requerido" }, 401);

        const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
        const { data: pc } = await supabaseAdmin
          .from("computers")
          .select("id, activo")
          .eq("agent_token", token)
          .maybeSingle();
        if (!pc || !pc.activo) return json({ error: "Computador no autorizado" }, 403);

        const parsed = Esquema.safeParse(await request.json().catch(() => null));
        if (!parsed.success) return json({ error: "Payload inválido" }, 400);
        const { documentId, estado, mensaje } = parsed.data;

        const { data: doc } = await supabaseAdmin
          .from("documents")
          .select("id, computer_id, operator_id")
          .eq("id", documentId)
          .maybeSingle();
        if (!doc || doc.computer_id !== pc.id) return json({ error: "Documento no encontrado" }, 404);

        const { error } = await supabaseAdmin
          .from("documents")
          .update({
            status: estado,
            error_message: estado.startsWith("error") ? (mensaje ?? "Error en el agente") : null,
            completed_at: estado.startsWith("error") ? null : new Date().toISOString(),
          })
          .eq("id", documentId);
        if (error) return json({ error: error.message }, 500);

        await supabaseAdmin.from("operation_logs").insert({
          document_id: documentId,
          operator_id: doc.operator_id,
          evento: `Agente: ${estado}`,
          detalle: mensaje ?? null,
        });

        return json({ ok: true });
      },
    },
  },
});