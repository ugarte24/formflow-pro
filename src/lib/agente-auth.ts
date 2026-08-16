/** Autorización del agente Windows: sesión de usuario (preferido) o PC legado. */

export type AgenteAuthUser = {
  mode: "user";
  userId: string;
  email: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabaseAdmin: any;
};

export type AgenteAuthComputer = {
  mode: "computer";
  pc: { id: string; nombre: string; codigo: string; activo: boolean };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabaseAdmin: any;
};

export type AgenteAuthOk = AgenteAuthUser | AgenteAuthComputer;
export type AgenteAuthResult = AgenteAuthOk | { error: Response };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function bearerToken(request: Request): string | null {
  const h = request.headers.get("authorization")?.trim();
  if (!h) return null;
  const m = /^Bearer\s+(.+)$/i.exec(h);
  return m?.[1]?.trim() || null;
}

/**
 * Auth del agente (prioridad):
 * 1) Authorization: Bearer <access_token> — mismas credenciales que la web
 * 2) x-computer-code — legado
 * 3) x-agent-token — legado
 */
export async function autorizarAgente(request: Request): Promise<AgenteAuthResult> {
  const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

  const jwt = bearerToken(request);
  if (jwt) {
    const { data, error } = await supabaseAdmin.auth.getUser(jwt);
    if (error || !data.user) {
      return { error: json({ error: "Sesión inválida o expirada. Vuelva a iniciar sesión." }, 401) };
    }

    const { data: perfil } = await supabaseAdmin
      .from("profiles")
      .select("id, activo")
      .eq("id", data.user.id)
      .maybeSingle();

    if (perfil && perfil.activo === false) {
      return { error: json({ error: "Usuario desactivado. Contacte al administrador." }, 403) };
    }

    return {
      mode: "user",
      userId: data.user.id,
      email: data.user.email ?? null,
      supabaseAdmin,
    };
  }

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
        { error: "Indique Authorization Bearer (login) o x-computer-code legado" },
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
  return { mode: "computer", pc, supabaseAdmin };
}
