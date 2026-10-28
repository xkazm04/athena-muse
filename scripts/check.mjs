// Docs gate: every relative markdown link resolves; no machine-absolute paths in committed text.
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, extname } from "node:path";

const SKIP = new Set([".git", "node_modules", ".spark", ".contest", "reference"]);
const files = [];
(function walk(d) {
  for (const n of readdirSync(d)) {
    if (SKIP.has(n)) continue;
    const p = join(d, n);
    statSync(p).isDirectory() ? walk(p) : extname(p) === ".md" && files.push(p);
  }
})(".");

const bad = [];
for (const f of files) {
  const text = readFileSync(f, "utf8");
  if (/[A-Za-z]:\Users\|\/Users\/[a-z]+\//.test(text)) bad.push(`${f}: machine-absolute path`);
  for (const m of text.matchAll(/\]\(([^)#\s]+)(#[^)]*)?\)/g)) {
    const t = m[1];
    if (/^[a-z]+:/i.test(t)) continue;
    if (!existsSync(resolve(dirname(f), t))) bad.push(`${f}: broken link ${t}`);
  }
}
console.log(`${files.length} markdown files checked`);
if (bad.length) { console.error(bad.join("\n")); process.exit(1); }
console.log("docs gate green");
