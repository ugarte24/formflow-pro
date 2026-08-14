import { createStart } from "@tanstack/react-start";
import { attachSupabaseAuth } from "@/integrations/supabase/auth-attacher";

/**
 * En Vercel/Nitro, createMiddleware / createCsrfMiddleware de TanStack
 * llegan rotos (undefined). Definimos start.ts para optar por fuera del
 * CSRF automático y solo dejamos el middleware de auth en client.
 */
export const startInstance = createStart(() => ({
  functionMiddleware: [attachSupabaseAuth],
  requestMiddleware: [],
}));
