#!/usr/bin/env node
// Generate src/schemas.generated.ts (the spec schemas, embedded) and
// src/types.generated.ts (TypeScript types) from spec/schemas/*/*.schema.json.
// The JSON schemas are the single source of truth.
//
//   node scripts/gen-schemas.mjs           write the two files
//   node scripts/gen-schemas.mjs --check   exit 1 if the files differ from the schemas (drift check)
//
// No dependency: a small schema-to-type converter for the keywords the spec schemas use.

import { readFileSync, readdirSync, writeFileSync, existsSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = join(here, "..");
const repo = join(pkg, "..", "..");
const schemaRoot = join(repo, "spec", "schemas");
const outSchemas = join(pkg, "src", "schemas.generated.ts");
const outTypes = join(pkg, "src", "types.generated.ts");
const check = process.argv.includes("--check");

const HEADER = "// GENERATED FILE. Do not edit. Source: spec/schemas/*/*.schema.json.\n// Regenerate: npm run gen:schemas (sdk/typescript). Check: npm run check:schemas.\n";

function listSchemas() {
  const out = [];
  for (const dir of readdirSync(schemaRoot).sort()) {
    const p = join(schemaRoot, dir);
    if (!statSync(p).isDirectory()) continue;
    for (const f of readdirSync(p).sort()) {
      if (!f.endsWith(".schema.json")) continue;
      out.push({ key: `${dir}/${f.replace(/\.schema\.json$/, "")}`, file: join(p, f), dir, name: f.replace(/\.schema\.json$/, "") });
    }
  }
  return out;
}

const pascal = (s) => s.split(/[^A-Za-z0-9]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join("");
function typeName(dir, name) {
  const prefix = dir.startsWith("nts-") ? "Nts" : pascal(dir); // fep-0001 -> Fep0001
  return prefix + pascal(name);
}

const lit = (v) => JSON.stringify(v);
const PRIM = { string: "string", number: "number", integer: "number", boolean: "boolean", null: "null" };

/** TypeScript type of a schema (structural keywords only; conditions and `not` are not types). */
function tsType(s, indent) {
  if (s === true || s === undefined) return "unknown";
  if (s === false) return "never";
  if (s.const !== undefined) return lit(s.const);
  if (s.enum) return s.enum.map(lit).join(" | ");
  const variants = s.oneOf ?? s.anyOf;
  let base;
  const types = s.type === undefined ? (s.properties ? ["object"] : []) : Array.isArray(s.type) ? s.type : [s.type];
  if (!types.length) base = "unknown";
  else {
    base = types.map((t) => {
      if (t === "array") return `${wrap(tsType(s.items, indent))}[]`;
      if (t === "object") return objType(s, indent);
      return PRIM[t] ?? "unknown";
    }).join(" | ");
  }
  if (variants && variants.some((v) => v.type || v.properties || v.const !== undefined || v.enum)) {
    return `${wrap(base)} & (${variants.map((v) => wrap(tsType(v, indent))).join(" | ")})`;
  }
  return base;
}
const wrap = (t) => (/[|&]/.test(t) && !/^\{[\s\S]*\}$/.test(t) ? `(${t})` : t);

function objType(s, indent) {
  const props = s.properties ?? {};
  const req = new Set(s.required ?? []);
  const pad = "  ".repeat(indent + 1);
  const lines = Object.entries(props).map(([k, v]) => {
    const doc = v && typeof v === "object" && v.description ? `${pad}/** ${v.description} */\n` : "";
    const key = /^[A-Za-z_$][\w$]*$/.test(k) ? k : lit(k);
    return `${doc}${pad}${key}${req.has(k) ? "" : "?"}: ${tsType(v, indent + 1)};`;
  });
  if (s.additionalProperties === false) {
    // closed object
  } else {
    lines.push(`${pad}/** Unknown keys are allowed (a consumer ignores them). */\n${pad}[key: string]: unknown;`);
  }
  if (!Object.keys(props).length && s.additionalProperties !== false) return "Record<string, unknown>";
  return `{\n${lines.join("\n")}\n${"  ".repeat(indent)}}`;
}

function generate() {
  const list = listSchemas();
  const schemas = {};
  for (const { key, file } of list) schemas[key] = JSON.parse(readFileSync(file, "utf8"));
  const keys = Object.keys(schemas);
  let a = HEADER + "/* eslint-disable */\n\n";
  a += `/** The spec schemas (${keys.length}), keyed by "<folder>/<name>". */\n`;
  a += `export const SCHEMAS = ${JSON.stringify(schemas, null, 1)} as const;\n\n`;
  a += `export type SchemaKey = ${keys.map(lit).join(" | ")};\n`;
  let b = HEADER + "/* eslint-disable */\n\n";
  b += "// Each type comes from one schema. Conditional rules (if/then, not) and the\n// semantic rules of the conformance profiles are not part of the types.\n\n";
  const names = [];
  for (const { key, dir, name } of list) {
    const s = schemas[key];
    const tn = typeName(dir, name);
    names.push([key, tn]);
    b += `/** ${s.title ?? key}${s.description ? `\n *\n * ${s.description}` : ""}\n *\n * Source: spec/schemas/${key}.schema.json */\n`;
    const t = tsType(s, 0);
    b += t.startsWith("{") ? `export interface ${tn} ${t}\n\n` : `export type ${tn} = ${t};\n\n`;
  }
  b += "/** Type name of each schema key. */\nexport interface SchemaTypes {\n" + names.map(([k, t]) => `  ${lit(k)}: ${t};`).join("\n") + "\n}\n";
  return { [outSchemas]: a, [outTypes]: b };
}

const files = generate();
if (check) {
  const drift = Object.entries(files).filter(([p, txt]) => !existsSync(p) || readFileSync(p, "utf8").replace(/\r\n/g, "\n") !== txt);
  if (drift.length) {
    console.error(`schema drift: ${drift.map(([p]) => relative(pkg, p)).join(", ")} differ from spec/schemas. Run: npm run gen:schemas`);
    process.exit(1);
  }
  console.log(`schemas OK: ${Object.keys(JSON.parse(JSON.stringify(listSchemas().map((x) => x.key)))).length} schemas, generated types match`);
} else {
  for (const [p, txt] of Object.entries(files)) writeFileSync(p, txt);
  console.log(`wrote ${Object.keys(files).map((p) => relative(pkg, p)).join(", ")}`);
}
