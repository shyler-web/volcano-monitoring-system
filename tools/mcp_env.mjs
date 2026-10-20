// Shared environment resolution for the Logisim MCP helper scripts.
//
// Everything is resolved at run time so the repository does not depend on
// one particular home directory:
//
//   LOGISIM_EXECUTABLE  path to the logisim-evolution launcher
//   LOGISIM_MCP_SERVER  path to the built MCP server entry point (dist/index.js)
//   LOGISIM_WORKSPACE   directory the MCP server is allowed to work in
//
// If a variable is not set, the usual local install locations are tried and
// finally whatever is on PATH.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const PROJECT_ROOT = resolve(here, "..");

function firstExisting(candidates) {
  for (const candidate of candidates) {
    if (candidate && existsSync(candidate)) return candidate;
  }
  return null;
}

export const LOGISIM_EXECUTABLE =
  process.env.LOGISIM_EXECUTABLE ??
  firstExisting([
    join(homedir(), "tools/logisim-evolution/bin/logisim-evolution"),
    "/opt/logisim-evolution/bin/logisim-evolution",
    "/usr/bin/logisim-evolution",
  ]) ??
  "logisim-evolution";

export const LOGISIM_MCP_SERVER =
  process.env.LOGISIM_MCP_SERVER ??
  firstExisting([
    join(homedir(), "tools/Logisim-Evolution-MCP-Server/dist/index.js"),
    join(PROJECT_ROOT, "tools/Logisim-Evolution-MCP-Server/dist/index.js"),
  ]) ?? "dist/index.js";

export const LOGISIM_WORKSPACE =
  process.env.LOGISIM_WORKSPACE ?? PROJECT_ROOT;

export const NODE =
  process.env.NODE ??
  firstExisting([join(homedir(), "tools/bin/node"), "/usr/bin/node"]) ??
  "node";

export const MCP_ENV = {
  ...process.env,
  LOGISIM_EXECUTABLE,
  LOGISIM_WORKSPACE,
};

// The MCP SDK is installed as a dependency of the MCP server checkout, so it
// is loaded from there rather than from this repository.
export async function loadSdk() {
  const sdkDir = join(
    dirname(LOGISIM_MCP_SERVER), "..", "node_modules",
    "@modelcontextprotocol", "sdk", "dist", "esm", "client",
  );
  const { Client } = await import(join(sdkDir, "index.js"));
  const { StdioClientTransport } = await import(join(sdkDir, "stdio.js"));
  return { Client, StdioClientTransport };
}
