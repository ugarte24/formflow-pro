/**
 * Rompe la dependencia circular Nitro/Rolldown:
 *   server-A.mjs  --imports--> server-A2.mjs (server_exports)
 *   server-A2.mjs --imports--> server-A.mjs (__exportAll)
 * que provoca: TypeError: __exportAll is not a function
 */
import fs from "node:fs";
import path from "node:path";

const roots = [
  path.join(process.cwd(), ".vercel", "output", "functions", "__server.func", "_ssr"),
  path.join(process.cwd(), ".output", "server", "_ssr"),
];

const EXPORT_ALL_HELPER = `var __defProp = Object.defineProperty;
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) __defProp(target, name, {
		get: all[name],
		enumerable: true
	});
	if (!no_symbols) __defProp(target, Symbol.toStringTag, { value: "Module" });
	return target;
};
`;

function fixDir(dir) {
  if (!fs.existsSync(dir)) return 0;
  let fixed = 0;
  const files = fs.readdirSync(dir).filter((f) => f.startsWith("server-") && f.endsWith(".mjs"));

  for (const file of files) {
    const full = path.join(dir, file);
    let src = fs.readFileSync(full, "utf8");
    let changed = false;

    // Big chunk: importa __exportAll del companion → inlinar helper
    const importExportAll = /import\s*\{\s*n\s+as\s+__exportAll\s*\}\s*from\s*"\.\/server-[^"]+\.mjs";?\s*/;
    if (importExportAll.test(src) && !src.includes("var __exportAll =")) {
      src = src.replace(importExportAll, EXPORT_ALL_HELPER + "\n");
      changed = true;
    }

    // Small companion: importa server_exports del big solo para reexportar
    // → convertir a re-export puro y definir __exportAll localmente
    const importServerExports = /^import\s*\{\s*s\s+as\s+server_exports\s*\}\s*from\s*"(\.\/server-[^"]+\.mjs)";?\s*/m;
    if (importServerExports.test(src)) {
      const companion = src.match(importServerExports)?.[1];
      src = src.replace(importServerExports, "");
      if (!src.includes("var __exportAll =")) {
        src = EXPORT_ALL_HELPER + "\n" + src;
      }
      // Reemplaza `export { __exportAll as n, server_exports as t };`
      src = src.replace(
        /export\s*\{\s*__exportAll\s+as\s+n\s*,\s*server_exports\s+as\s+t\s*\};?/,
        `export { __exportAll as n };\nexport { s as t } from "${companion}";`,
      );
      changed = true;
    }

    if (changed) {
      fs.writeFileSync(full, src);
      fixed++;
      console.log("[fix-ssr-circular]", file);
    }
  }
  return fixed;
}

let total = 0;
for (const dir of roots) total += fixDir(dir);
console.log(total === 0 ? "[fix-ssr-circular] Nada que parchear." : `[fix-ssr-circular] Corregidos: ${total}`);
