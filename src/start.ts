import { createStart, createMiddleware } from "@tanstack/react-start";

import { renderErrorPage } from "./lib/error-page";
import { attachSupabaseAuth } from "@/integrations/supabase/auth-attacher";

const errorMiddleware = createMiddleware().server(async ({ next }) => {
  try {
    return await next();
  } catch (error) {
    if (error != null && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    console.error(error);
    return new Response(renderErrorPage(), {
      status: 500,
      headers: { "content-type": "text/html; charset=utf-8" },
    });
  }
});

/**
 * CSRF para server functions.
 * No usamos createCsrfMiddleware de TanStack: en el bundle Nitro/Vercel
 * el export isomórfico llega como undefined ("createCsrfMiddleware is not a function").
 */
const csrfMiddleware = createMiddleware().server(async (ctx) => {
  const { next, request } = ctx;
  const handlerType = (ctx as { handlerType?: string }).handlerType;
  if (handlerType && handlerType !== "serverFn") {
    return next();
  }

  const fetchSite = request.headers.get("Sec-Fetch-Site");
  if (fetchSite !== null && fetchSite !== "same-origin" && fetchSite !== "none") {
    return new Response(JSON.stringify({ error: "CSRF blocked" }), {
      status: 403,
      headers: { "content-type": "application/json" },
    });
  }

  const origin = request.headers.get("Origin");
  if (origin !== null) {
    const expected = new URL(request.url).origin;
    if (origin !== expected) {
      return new Response(JSON.stringify({ error: "CSRF blocked" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      });
    }
  }

  return next();
});

export const startInstance = createStart(() => ({
  functionMiddleware: [attachSupabaseAuth],
  requestMiddleware: [errorMiddleware, csrfMiddleware],
}));
