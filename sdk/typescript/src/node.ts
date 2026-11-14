/**
 * Node-only helpers (file system). Import from `@fidetype/sdk/node`.
 * The core entry point (`@fidetype/sdk`) has no Node API.
 */

import { createReadStream } from "node:fs";
import { readFile, readdir, stat } from "node:fs/promises";
import { basename, join } from "node:path";
import { loadStream } from "./checks.js";
import type { ConsumedStream } from "./checks.js";
import { CONSUMERS, runVectors } from "./conformance.js";
import type { ProfileReport } from "./conformance.js";
import { readNtsEvents } from "./reader.js";
import { handleDecisions } from "./trust.js";
import type { HandledDecision } from "./trust.js";
import { parseNtsText } from "./reader.js";
import { checkStream } from "./index.js";

/** Read a file as bytes (a Uint8Array view, not a Buffer subclass in the API). */
export async function readBytes(path: string): Promise<Uint8Array> {
  const b = await readFile(path);
  return new Uint8Array(b.buffer, b.byteOffset, b.byteLength);
}

/** The reference consumer on a file (`.npz` or `.jsonl`). Throws StreamRejected. */
export async function loadStreamFile(path: string): Promise<ConsumedStream> {
  return loadStream(basename(path), await readBytes(path));
}

/** Run the v0.1 checks on a file. */
export async function checkStreamFile(path: string, level: "core" | "trust-ready" | "provenance" = "core") {
  return checkStream(basename(path), await readBytes(path), level);
}

/** Stream the events of a JSON Lines file (constant memory). */
export function streamEventsFromFile(path: string): AsyncGenerator<Record<string, unknown>> {
  return readNtsEvents(createReadStream(path) as unknown as AsyncIterable<Uint8Array>);
}

/** Read a decision log (or any JSON Lines file of trust_decision events) and handle every decision. */
export async function handleDecisionFile(path: string): Promise<HandledDecision[]> {
  return handleDecisions(parseNtsText(await readBytes(path)));
}

/** Profiles present under a conformance folder (`spec/conformance`), in a fixed order. */
export async function listProfiles(conformanceDir: string): Promise<string[]> {
  const names = await readdir(conformanceDir);
  const out: string[] = [];
  for (const n of names.sort()) {
    const p = join(conformanceDir, n);
    if ((await stat(p)).isDirectory() && Object.prototype.hasOwnProperty.call(CONSUMERS, n)) {
      try {
        await stat(join(p, "manifest.json"));
        out.push(n);
      } catch {
        // no manifest: not a vector folder
      }
    }
  }
  // v0.1 first, then the FEP profiles.
  return out.sort((a, b) => (a === "v0.1" ? -1 : b === "v0.1" ? 1 : a < b ? -1 : 1));
}

/** Run one profile over the vectors in `dir` (a folder with manifest.json). */
export async function runProfileDir(profile: string, dir: string): Promise<ProfileReport> {
  return runVectors(profile, (file) => readBytes(join(dir, file)));
}
