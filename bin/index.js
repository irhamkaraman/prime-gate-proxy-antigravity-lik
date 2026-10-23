#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

// Read local version
let currentVersion = "1.2.5";
try {
  const pkg = JSON.parse(fs.readFileSync(path.join(projectRoot, "package.json"), "utf8"));
  if (pkg.version) currentVersion = pkg.version;
} catch {}

function parseSemver(v) {
  return v.replace(/^v/, "").split(".").map(x => parseInt(x, 10) || 0);
}

function isNewer(latest, current) {
  const l = parseSemver(latest);
  const c = parseSemver(current);
  for (let i = 0; i < Math.max(l.length, c.length); i++) {
    const lPart = l[i] ?? 0;
    const cPart = c[i] ?? 0;
    if (lPart > cPart) return true;
    if (lPart < cPart) return false;
  }
  return false;
}

async function checkNpmUpdate() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1500);
    const res = await fetch("https://registry.npmjs.org/prime-gate-antigravity/latest", {
      signal: controller.signal,
      headers: { "Accept": "application/json" }
    });
    clearTimeout(timeout);
    if (!res.ok) return;
    const data = await res.json();
    const latestVersion = data.version;
    if (latestVersion && isNewer(latestVersion, currentVersion)) {
      console.log(`\n\x1b[33m╭──────────────────────────────────────────────────────────────╮\x1b[0m`);
      console.log(`\x1b[33m│\x1b[0m  \x1b[1m🔔 Update available on npm\x1b[0m: \x1b[31m${currentVersion}\x1b[0m \x1b[2m→\x1b[0m \x1b[32m${latestVersion}\x1b[0m                         \x1b[33m│\x1b[0m`);
      console.log(`\x1b[33m│\x1b[0m  Run \x1b[36mnpx prime-gate-antigravity@latest\x1b[0m or                     \x1b[33m│\x1b[0m`);
      console.log(`\x1b[33m│\x1b[0m  \x1b[36mnpm install -g prime-gate-antigravity@latest\x1b[0m to update       \x1b[33m│\x1b[0m`);
      console.log(`\x1b[33m╰──────────────────────────────────────────────────────────────╯\x1b[0m\n`);
    }
  } catch {
    // Fail silently so execution is never disrupted
  }
}

async function main() {
  const args = process.argv.slice(2);

  // Check npm update concurrently with short timeout
  await checkNpmUpdate();

  // If user calls 'ui', run the UI server directly
  if (args[0] === "ui") {
    const uiServer = path.join(projectRoot, "ui", "server.js");
    const child = spawn(process.execPath, [uiServer, ...args.slice(1)], {
      stdio: "inherit",
      cwd: projectRoot
    });
    child.on("exit", code => process.exit(code ?? 0));
  } else {
    // Otherwise pass through to Python CLI
    const child = spawn("python", ["-m", "prime_gate.cli", ...args], {
      stdio: "inherit",
      cwd: projectRoot,
      shell: true
    });
    child.on("exit", code => process.exit(code ?? 0));
  }
}

main();
