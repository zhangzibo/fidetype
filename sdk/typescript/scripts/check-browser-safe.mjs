#!/usr/bin/env node
// Check that the core build (dist/, without node.js) uses no Node-only API:
// no "node:" imports, no require(), no process / Buffer / __dirname globals.
// The core is also compiled with `types: []` (no @types/node), so a Node API
// in src/ (except src/node.ts) is a compile error.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist/", import.meta.url));
const bad = [];
const walk = (d) => {
  for (const f of readdirSync(d)) {
    const p = join(d, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (p.endsWith(".js") && relative(dist, p) !== "node.js") {
      const src = readFileSync(p, "utf8");
      for (const [re, what] of [[/from\s+["']node:/, "node: import"], [/\brequire\s*\(/, "require()"], [/\bprocess\./, "process"], [/\bBuffer\b/, "Buffer"], [/__dirname|__filename/, "__dirname"]]) {
        if (re.test(src)) bad.push(`${relative(dist, p)}: ${what}`);
      }
      if (/from\s+["']\.\/node\.js["']/.test(src)) bad.push(`${relative(dist, p)}: imports node.js`);
    }
  }
};
walk(dist);
if (bad.length) {
  console.error("browser-safety check FAILED:\n  " + bad.join("\n  "));
  process.exit(1);
}
console.log("browser-safety check OK: the core build uses no Node-only API");
