#!/usr/bin/env node
// Describe a component with specific attributes: node tools/mcp_desc2.mjs <lib> <name> '<json-attrs>' [...]
import { LOGISIM_MCP_SERVER, MCP_ENV, NODE, loadSdk } from "./mcp_env.mjs";

const { Client, StdioClientTransport } = await loadSdk();

const argv = process.argv.slice(2);
const specs = [];
for (let i = 0; i + 2 < argv.length; i += 3) specs.push([argv[i], argv[i + 1], JSON.parse(argv[i + 2])]);

const client = new Client({ name: "mcp-desc2", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: NODE,
  args: [LOGISIM_MCP_SERVER],
  env: MCP_ENV,
});
await client.connect(transport);
for (const [lib, name, attrs] of specs) {
  const res = await client.callTool({
    name: "logisim_describe_component",
    arguments: { library: lib, name, attributes: attrs },
  });
  const sc = res.structuredContent ?? res.content?.[0]?.text;
  const text = typeof sc === "string" ? sc : JSON.stringify(sc);
  let j = {};
  try { j = JSON.parse(text); } catch { console.log(text); continue; }
  console.log(`\n== lib ${lib} / ${name} ${JSON.stringify(attrs)}`);
  console.log("  attrs:", (j.attributes ?? []).map((a) => `${a.name}=${a.default ?? ""}`).join(" "));
  console.log("  ports:", (j.ports ?? []).map((p) => `${p.id}:${p.role}@(${p.offsetFromAnchor?.x},${p.offsetFromAnchor?.y})w${p.width}`).join(" "));
  console.log("  bounds:", JSON.stringify(j.boundsRelativeToAnchor));
}
await client.close();
