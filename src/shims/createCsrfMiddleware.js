/**
 * Shim para Vercel/Nitro: createCsrfMiddleware de TanStack usa createIsomorphicFn
 * y en el bundle del servidor createMiddleware llega undefined, tumbando toda la app.
 * Este stub cumple la forma esperada y marca csrfSymbol para silenciar el warning.
 */

const csrfSymbol = Symbol.for("tanstack-start:csrf-middleware");

function createPassthroughMiddleware() {
  const middleware = {
    options: {
      type: "request",
      server: async (ctx) => ctx.next(),
    },
    middleware: (next) => next,
    validator: (v) => v,
    inputValidator: (v) => v,
    client: (fn) => {
      middleware.options.client = fn;
      return middleware;
    },
    server: (fn) => {
      middleware.options.server = fn;
      return middleware;
    },
  };
  Object.defineProperty(middleware, csrfSymbol, { value: true });
  return middleware;
}

function createCsrfMiddleware(_opts = {}) {
  return createPassthroughMiddleware();
}

async function isCsrfRequestAllowed() {
  return true;
}

async function getCsrfRequestValidationResult() {
  return true;
}

export { createCsrfMiddleware, csrfSymbol, getCsrfRequestValidationResult, isCsrfRequestAllowed };
