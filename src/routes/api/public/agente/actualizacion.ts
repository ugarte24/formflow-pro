import { createFileRoute } from "@tanstack/react-router";

const BUCKET = "agente";
const PATH = "releases/DigitalizadorAgent-Setup.zip";
const META_PATH = "releases/version.json";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

export const Route = createFileRoute("/api/public/agente/actualizacion")({
  server: {
    handlers: {
      GET: async () => {
        try {
          const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

          let version = "0.0.0";
          let bytes: number | null = null;
          let publicado_at: string | null = null;

          const metaRes = await supabaseAdmin.storage.from(BUCKET).download(META_PATH);
          if (metaRes.data && !metaRes.error) {
            try {
              const raw = metaRes.data;
              const text =
                typeof (raw as Blob).text === "function"
                  ? await (raw as Blob).text()
                  : new TextDecoder().decode(raw as ArrayBuffer);
              const meta = JSON.parse(text) as {
                version?: string;
                bytes?: number;
                publicado_at?: string;
              };
              if (meta.version) version = meta.version;
              if (typeof meta.bytes === "number") bytes = meta.bytes;
              if (meta.publicado_at) publicado_at = meta.publicado_at;
            } catch {
              /* ignore */
            }
          } else {
            return json({ disponible: false, error: "No hay versión publicada" }, 404);
          }

          const { data, error } = await supabaseAdmin.storage
            .from(BUCKET)
            .createSignedUrl(PATH, 60 * 60, {
              download: `DigitalizadorAgent-Setup-v${version}.zip`,
            });
          if (error || !data?.signedUrl) {
            return json({ disponible: false, error: error?.message ?? "Sin URL de descarga" }, 404);
          }

          return json({
            disponible: true,
            version,
            bytes,
            publicado_at,
            url: data.signedUrl,
          });
        } catch (e) {
          return json(
            { disponible: false, error: e instanceof Error ? e.message : "Error" },
            500,
          );
        }
      },
    },
  },
});
