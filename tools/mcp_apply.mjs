#!/usr/bin/env node
// Apply a batch payload (JSON file) to a Logisim project through the MCP server.
// Usage: node tools/mcp_apply.mjs <batch.json>
import { readFileSync } from "node:fs";
import { LOGISIM_MCP_SERVER, MCP_ENV, NODE, loadSdk } from "./mcp_env.mjs";

const { Client, StdioClientTransport } = await loadSdk();

const batch = JSON.parse(readFileSync(process.argv[2], "utf8"));
const client = new Client({ name: "mcp-apply", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: NODE,
  args: [LOGISIM_MCP_SERVER],
  env: MCP_ENV,
});
await client.connect(transport);
const res = await client.callTool({ name: "logisim_apply_batch", arguments: batch });
const sc = res.structuredContent ?? res.content?.[0]?.text;
console.log(typeof sc === "string" ? sc : JSON.stringify(sc, null, 2));
await client.close();
