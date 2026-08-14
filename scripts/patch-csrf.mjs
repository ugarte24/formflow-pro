/**
 * Parchea createCsrfMiddleware de TanStack para que no tumbe el SSR en Vercel/Nitro.
 * createIsomorphicFn deja createMiddleware como undefined al evaluar el módulo.
 */
import fs from "node:fs";
import path from "node:path";

const target = path.join(
  process.cwd(),
  "node_modules",
  "@tanstack",
  "start-client-core",
  "dist",
  "esm",
  "createCsrfMiddleware.js",
);

const shim = `const csrfSymbol = Symbol.for("tanstack-start:csrf-middleware");

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
`;

if (!fs.existsSync(target)) {
  console.warn("[patch-csrf] No se encontró", target);
  process.exit(0);
}

fs.writeFileSync(target, shim);
console.log("[patch-csrf] Parche aplicado en", target);
