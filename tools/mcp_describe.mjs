#!/usr/bin/env node
// Batch-inspect Logisim components through the MCP server in one connection.
// Usage: node tools/mcp_describe.mjs <lib> <name> [<lib> <name> ...]
import { LOGISIM_MCP_SERVER, MCP_ENV, NODE, loadSdk } from "./mcp_env.mjs";

const { Client, StdioClientTransport } = await loadSdk();

const pairs = [];
const argv = process.argv.slice(2);
for (let i = 0; i + 1 < argv.length; i += 2) pairs.push([argv[i], argv[i + 1]]);

const client = new Client({ name: "mcp-describe", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: NODE,
  args: [LOGISIM_MCP_SERVER],
  env: MCP_ENV,
});
await client.connect(transport);
for (const [lib, name] of pairs) {
  const res = await client.callTool({
    name: "logisim_describe_component",
    arguments: { library: lib, name },
  });
  const sc = res.structuredContent ?? res.content?.[0]?.text;
  const text = typeof sc === "string" ? sc : JSON.stringify(sc, null, 2);
  console.log(`\n======== lib ${lib} / ${name} ========`);
  try {
    const j = JSON.parse(text);
    console.log("supported:", j.supported, "| summary:", j.summary);
    console.log("attrs:", (j.attributes ?? []).map((a) => `${a.name}[${a.type}]${a.default !== undefined ? "=" + a.default : ""}${a.values ? "{" + a.values.join("|") + "}" : ""}${a.range ? "[" + a.range.join("..") + "]" : ""}`).join("  "));
    console.log("ports:", (j.ports ?? []).map((p) => `${p.id}:${p.role}@(${p.offsetFromAnchor?.x},${p.offsetFromAnchor?.y})w${p.width}${p.escape ? " esc=" + p.escape : ""}`).join("  "));
    console.log("bounds:", JSON.stringify(j.boundsRelativeToAnchor));
    console.log("notes:", (j.notes ?? []).join(" | "));
  } catch {
    console.log(text);
  }
}
await client.close();
