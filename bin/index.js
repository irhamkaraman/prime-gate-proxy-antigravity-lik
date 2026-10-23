#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

const args = process.argv.slice(2);

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
