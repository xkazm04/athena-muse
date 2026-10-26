// Toolchain preflight: run before the clock starts and again at T0. Prints versions, never secrets.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const TOOLS = [
  ["node", ["--version"], true],
  ["pnpm", ["--version"], true],
  ["uv", ["--version"], true],
  ["python", ["--version"], true],
  ["cargo", ["--version"], true],
  ["rustc", ["--version"], true],
  ["git", ["--version"], true],
  ["gh", ["--version"], false],
  ["claude", ["--version"], false],
];

let missing = 0;
for (const [cmd, args, required] of TOOLS) {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: process.platform === "win32" });
  const out = (r.stdout || r.stderr || "").split("\n")[0].trim();
  const ok = r.status === 0;
  if (!ok && required) missing++;
  console.log(`${ok ? "ok     " : required ? "MISSING" : "absent "} ${cmd.padEnd(7)} ${ok ? out : ""}`);
}

// The key is reported as present/absent only.
let key = Boolean(process.env.META_API_KEY);
if (!key && existsSync(".env")) key = /^META_API_KEY=\S+/m.test(readFileSync(".env", "utf8"));
console.log(`${key ? "ok     " : "absent "} META_API_KEY ${key ? "set" : "not set (WP1 day-1 probe needs it)"}`);

console.log(existsSync(".git") ? "note: .git exists - T0 init already done" : "note: no .git yet - expected until T0 (docs/hackathon/T0.md)");
process.exit(missing ? 1 : 0);
