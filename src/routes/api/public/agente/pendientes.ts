import { createFileRoute } from "@tanstack/react-router";
import { partirApellidos, generarCelularAleatorio } from "@/lib/ruat";
import { autorizarAgente } from "@/lib/agente-auth";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

export const Route = createFileRoute("/api/public/agente/pendientes")({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const auth = await autorizarAgente(request);
        if ("error" in auth) return auth.error;
        const { pc, supabaseAdmin } = auth;

        const { data, error } = await supabaseAdmin
          .from("documents")
          .select(
            "id, numero_documento, nombres, apellidos, genero, estado_civil, fecha_nacimiento, barrio, avenida, numero_puerta, image_path, foto_path, sent_at, operator_id",
          )
          .eq("computer_id", pc.id)
          .eq("status", "confirmado")
          .not("foto_path", "is", null)
          .order("sent_at", { ascending: true })
          .limit(10);
        if (error) return json({ error: error.message }, 500);

        // Solo trámites de operadores activos
        const operatorIds = [...new Set((data ?? []).map((d) => d.operator_id).filter(Boolean))] as string[];
        let activos = new Set<string>();
        if (operatorIds.length > 0) {
          const { data: perfiles } = await supabaseAdmin
            .from("profiles")
            .select("id, activo")
            .in("id", operatorIds);
          activos = new Set((perfiles ?? []).filter((p) => p.activo !== false).map((p) => p.id));
        }

        const listos = (data ?? []).filter(
          (d) => !!d.foto_path && (!d.operator_id || activos.has(d.operator_id)),
        );

        if (listos.length > 0) {
          await supabaseAdmin
            .from("documents")
            .update({ status: "enviado_pc" })
            .in(
              "id",
              listos.slice(0, 5).map((d) => d.id),
            );
        }

        const aEnviar = listos.slice(0, 5);
        const documentos = await Promise.all(
          aEnviar.map(async (d) => {
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
