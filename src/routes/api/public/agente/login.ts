import { createFileRoute } from "@tanstack/react-router";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";
import type { Database } from "@/integrations/supabase/types";

const Esquema = z.object({
  email: z.string().email().max(200),
  password: z.string().min(6).max(200),
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function authClient() {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_PUBLISHABLE_KEY"];
  if (!url || !key) throw new Error("Faltan SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY");
  return createClient<Database>(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export const Route = createFileRoute("/api/public/agente/login")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const parsed = Esquema.safeParse(await request.json().catch(() => null));
        if (!parsed.success) return json({ error: "Email y contraseña requeridos" }, 400);

        try {
          const supabase = authClient();
          const { data, error } = await supabase.auth.signInWithPassword({
            email: parsed.data.email.trim().toLowerCase(),
            password: parsed.data.password,
          });
          if (error || !data.session || !data.user) {
            return json({ error: "Credenciales incorrectas" }, 401);
          }

          const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
          const { data: perfil } = await supabaseAdmin
            .from("profiles")
            .select("nombre_completo, activo")
            .eq("id", data.user.id)
            .maybeSingle();

          if (perfil && perfil.activo === false) {
            return json({ error: "Usuario desactivado. Contacte al administrador." }, 403);
          }

          return json({
            access_token: data.session.access_token,
            refresh_token: data.session.refresh_token,
            expires_in: data.session.expires_in,
            expires_at: data.session.expires_at,
            user: {
              id: data.user.id,
              email: data.user.email,
              nombre: perfil?.nombre_completo ?? null,
            },
          });
        } catch (e) {
          return json({ error: e instanceof Error ? e.message : "Error de login" }, 500);
        }
      },
    },
  },
});
