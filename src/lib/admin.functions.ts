import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

async function asegurarAdmin(supabase: any, userId: string) {
  const { data } = await supabase.rpc("has_role", { _user_id: userId, _role: "admin" });
  if (!data) throw new Error("Solo un administrador puede realizar esta acción");
}

export const obtenerTokenAgente = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: { computerId: string }) => {
    if (!input?.computerId) throw new Error("Falta el computador");
    return input;
  })
  .handler(async ({ data, context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: pc, error } = await supabaseAdmin
      .from("computers")
      .select("agent_token")
      .eq("id", data.computerId)
      .single();
    if (error) throw new Error(error.message);
    return { token: pc.agent_token as string };
  });

export const rotarTokenAgente = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: { computerId: string }) => {
    if (!input?.computerId) throw new Error("Falta el computador");
    return input;
  })
  .handler(async ({ data, context }) => {
    await asegurarAdmin(context.supabase, context.userId);
    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const nuevo = crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
    const { error } = await supabaseAdmin
      .from("computers")
      .update({ agent_token: nuevo })
      .eq("id", data.computerId);
    if (error) throw new Error(error.message);
    return { token: nuevo };
  });