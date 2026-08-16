import { createFileRoute } from "@tanstack/react-router";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";
import type { Database } from "@/integrations/supabase/types";

const Esquema = z.object({
  refresh_token: z.string().min(20).max(2000),
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

export const Route = createFileRoute("/api/public/agente/refresh")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const parsed = Esquema.safeParse(await request.json().catch(() => null));
        if (!parsed.success) return json({ error: "refresh_token requerido" }, 400);

        try {
          const supabase = authClient();
          const { data, error } = await supabase.auth.refreshSession({
            refresh_token: parsed.data.refresh_token,
          });
          if (error || !data.session || !data.user) {
            return json({ error: "Sesión expirada. Vuelva a iniciar sesión." }, 401);
          }

          return json({
            access_token: data.session.access_token,
            refresh_token: data.session.refresh_token,
            expires_in: data.session.expires_in,
            expires_at: data.session.expires_at,
            user: {
              id: data.user.id,
              email: data.user.email,
            },
          });
        } catch (e) {
          return json({ error: e instanceof Error ? e.message : "Error al renovar sesión" }, 500);
        }
      },
    },
  },
});
