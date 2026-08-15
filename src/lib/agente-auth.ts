/** Autorización del agente Windows: por código de PC (sin token). */

export type AgenteAuthOk = {
  pc: { id: string; nombre: string; codigo: string; activo: boolean };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabaseAdmin: any;
};

export type AgenteAuthResult = AgenteAuthOk | { error: Response };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

/**
 * Auth del agente:
 * 1) Preferido: header `x-computer-code` (ej. PC-VEN-01) — sin secretos en el PC
 * 2) Compat: header `x-agent-token` (legado)
 * El PC debe estar activo. Si no, 403.
 */
export async function autorizarAgente(request: Request): Promise<AgenteAuthResult> {
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

  const codigo = request.headers.get("x-computer-code")?.trim().toUpperCase();
  const token = request.headers.get("x-agent-token")?.trim();

  let pc: { id: string; nombre: string; codigo: string; activo: boolean } | null = null;

  if (codigo && codigo.length >= 2) {
    const { data } = await supabaseAdmin
      .from("computers")
      .select("id, nombre, codigo, activo")
      .eq("codigo", codigo)
      .maybeSingle();
    pc = data;
  } else if (token && token.length >= 20) {
    const { data } = await supabaseAdmin
      .from("computers")
      .select("id, nombre, codigo, activo")
      .eq("agent_token", token)
      .maybeSingle();
    pc = data;
  } else {
    return {
      error: json(
        { error: "Indique x-computer-code (código del PC) o x-agent-token legado" },
        401,
      ),
    };
  }

  if (!pc) return { error: json({ error: "Computador no encontrado" }, 403) };
  if (!pc.activo) {
    return {
      error: json(
        { error: "Computador desactivado por el administrador. No se procesan trámites." },
        403,
      ),
    };
  }

  await supabaseAdmin.from("computers").update({ last_seen_at: new Date().toISOString() }).eq("id", pc.id);
  return { pc, supabaseAdmin };
}
