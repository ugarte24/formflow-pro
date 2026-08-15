import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const BUCKET = "agente";
const PATH = "releases/DigitalizadorAgent-Setup.zip";

async function asegurarAdmin(supabase: any, userId: string) {
  const { data } = await supabase.rpc("has_role", { _user_id: userId, _role: "admin" });
  if (!data) throw new Error("Solo un administrador puede realizar esta acción");
}

export const estadoInstaladorAgente = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).list("releases", {
      search: "DigitalizadorAgent-Setup.zip",
      limit: 5,
    });
    if (error) throw new Error(error.message);
    const file = (data ?? []).find((f) => f.name === "DigitalizadorAgent-Setup.zip");
    if (!file) return { disponible: false as const };

    return {
      disponible: true as const,
      nombre: file.name,
      bytes: file.metadata?.size ?? null,
      actualizado: file.updated_at ?? file.created_at ?? null,
    };
  });

export const urlDescargaInstaladorAgente = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data, error } = await supabaseAdmin.storage.from(BUCKET).createSignedUrl(PATH, 60 * 30);
    if (error || !data?.signedUrl) {
      throw new Error(error?.message ?? "No hay instalador publicado. Subí el ZIP desde Admin o con el script de publicación.");
    }
    return { url: data.signedUrl, nombre: "DigitalizadorAgent-Setup.zip" };
  });
