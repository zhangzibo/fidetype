// Release check (docs/RELEASING.md): the package version has one value everywhere.
//   - package.json "version" must equal SDK_VERSION in src/index.ts (and dist/index.js when built);
//   - LICENSE must be a byte copy of the repository LICENSE.
// Exit 0 = OK, 1 = mismatch.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const errors = [];
const re = /export const SDK_VERSION = "([^"]+)"/;
for (const f of ["src/index.ts", "dist/index.js"]) {
  const p = join(root, f);
  if (!existsSync(p)) continue;
  const m = readFileSync(p, "utf8").match(re);
  if (!m) errors.push(`${f}: SDK_VERSION not found`);
  else if (m[1] !== pkg.version) errors.push(`${f}: SDK_VERSION ${m[1]} != package.json version ${pkg.version}`);
}
const lic = join(root, "LICENSE");
const repoLic = join(root, "..", "..", "LICENSE");
if (!existsSync(lic)) errors.push("LICENSE is missing (copy the repository LICENSE)");
else if (existsSync(repoLic) && !readFileSync(lic).equals(readFileSync(repoLic))) errors.push("LICENSE differs from the repository LICENSE");
if (errors.length) {
  for (const e of errors) console.error(`check-version: ${e}`);
  process.exit(1);
}
console.log(`check-version: OK (${pkg.name} ${pkg.version})`);
