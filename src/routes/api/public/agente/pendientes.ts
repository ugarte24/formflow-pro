import { createFileRoute } from "@tanstack/react-router";
import { partirApellidos, generarCelularAleatorio } from "@/lib/ruat";

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
            "id, numero_documento, nombres, apellidos, genero, estado_civil, fecha_nacimiento, barrio, avenida, numero_puerta, image_path, foto_path, sent_at",
          )
          .eq("computer_id", pc.id)
          .eq("status", "confirmado")
          .not("foto_path", "is", null)
          .order("sent_at", { ascending: true })
          .limit(5);
        if (error) return json({ error: error.message }, 500);

        const listos = (data ?? []).filter((d) => !!d.foto_path);
        if (listos.length > 0) {
          await supabaseAdmin
            .from("documents")
            .update({ status: "enviado_pc" })
            .in(
              "id",
              listos.map((d) => d.id),
            );
        }

        const documentos = await Promise.all(
          listos.map(async (d) => {
            const { primer_apellido, segundo_apellido } = partirApellidos(d.apellidos);
            let foto_url: string | null = null;
            if (d.foto_path) {
              const { data: signed } = await supabaseAdmin.storage
                .from("documentos")
                .createSignedUrl(d.foto_path, 60 * 60);
              foto_url = signed?.signedUrl ?? null;
            }
            return {
              id: d.id,
              numero_documento: d.numero_documento,
              nombres: d.nombres,
              apellidos: d.apellidos,
              primer_apellido,
              segundo_apellido,
              genero: d.genero,
              estado_civil: d.estado_civil,
              fecha_nacimiento: d.fecha_nacimiento,
              barrio: d.barrio,
              avenida: d.avenida,
              numero_puerta: d.numero_puerta,
              telefono_celular: generarCelularAleatorio(),
              foto_url,
              foto_path: d.foto_path,
              sent_at: d.sent_at,
              instrucciones: {
                tipo_documento: "CEDULA DE IDENTIDAD",
                departamento_expedido: "",
                gestor_tramite: null,
                apoderado: "cancelar",
                imagenes: "solo_fotografia",
                si_existe_contribuyente: "asociar_y_completar_faltantes",
              },
            };
          }),
        );

        return json({ computador: pc.codigo, documentos });
      },
    },
  },
});
