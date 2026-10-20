#!/usr/bin/env node
// Drive the Logisim-evolution MCP server from the terminal.
// Usage: node tools/mcp_call.mjs <tool_name> '<json-args>' [--raw]
import { LOGISIM_MCP_SERVER, MCP_ENV, NODE, loadSdk } from "./mcp_env.mjs";

const { Client, StdioClientTransport } = await loadSdk();

const [, , toolName, argsJson, ...flags] = process.argv;
if (!toolName) {
  const client = new Client({ name: "mcp-cli", version: "1.0.0" });
  const transport = new StdioClientTransport({
    command: NODE,
    args: [LOGISIM_MCP_SERVER],
    env: MCP_ENV,
  });
  await client.connect(transport);
  const tools = await client.listTools();
  for (const t of tools.tools) {
    console.log(`\n### ${t.name}\n${t.description ?? ""}`);
    console.log(JSON.stringify(t.inputSchema, null, 2));
  }
  await client.close();
  process.exit(0);
}

const client = new Client({ name: "mcp-cli", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: NODE,
  args: [LOGISIM_MCP_SERVER],
  env: MCP_ENV,
});
await client.connect(transport);
const result = await client.callTool({
  name: toolName,
  arguments: argsJson ? JSON.parse(argsJson) : {},
});
if (flags.includes("--raw")) {
  console.log(JSON.stringify(result, null, 2));
} else {
  const sc = result.structuredContent;
  console.log(sc ? JSON.stringify(sc, null, 2) : JSON.stringify(result.content, null, 2));
}
await client.close();
