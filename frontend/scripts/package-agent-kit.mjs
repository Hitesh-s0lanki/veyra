import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { deflateRawSync } from "node:zlib";

const frontendRoot = resolve(import.meta.dirname, "..");
const projectRoot = resolve(frontendRoot, "..");
const outputRoot = resolve(frontendRoot, "public", "downloads");
const skillRoot = resolve(projectRoot, ".agent", "skills", "video-generation-mcp");

const files = [
  ["mcp_server.py", resolve(projectRoot, "mcp_server.py")],
  ["src/__init__.py", resolve(projectRoot, "src", "__init__.py")],
  ["src/config.py", resolve(projectRoot, "src", "config.py")],
  ["src/mcp_server.py", resolve(projectRoot, "src", "mcp_server.py")],
  ["skills/video-generation-mcp/SKILL.md", resolve(skillRoot, "SKILL.md")],
  ["skills/video-generation-mcp/references/prompting.md", resolve(skillRoot, "references", "prompting.md")],
  ["AGENT_PROMPT.md", resolve(skillRoot, "assets", "AGENT_PROMPT.md")],
];

const setup = `# Video Generation MCP client setup

This bundle runs a local stdio MCP client for the Video Generation API. The API is hosted separately. Python 3.12 or 3.13 is recommended.

1. Extract this ZIP and open a terminal in the extracted folder.
2. Create a virtual environment: \`python -m venv .venv\`.
3. Install the client packages: \`.venv/Scripts/python -m pip install -r requirements-mcp.txt\` on Windows, or \`.venv/bin/python -m pip install -r requirements-mcp.txt\` on macOS/Linux.
4. In your MCP client's configuration, set the command to the absolute path of that virtual environment's Python, and set args to the absolute path of \`mcp_server.py\`.
5. Set \`VIDEO_API_BASE_URL\` to the current hosted API HTTPS URL, and \`VIDEO_API_TOKEN\` to a bearer token issued for your account. Keep the token private. The website's browser session is not an MCP token.
6. Install the entire \`skills/video-generation-mcp\` folder in your agent client's skills directory. Use \`AGENT_PROMPT.md\` as the agent's initial instruction if your client supports it.

The MCP server exposes seven tools. \`generate_video\` starts a billable job. \`download_video\` writes on the machine running this MCP process. Local image upload is restricted to \`VIDEO_MCP_IMAGE_ROOT\` (the extracted bundle directory by default); output defaults to its \`outputs\` directory.
`;

const requirements = "fastmcp>=4,<5\nhttpx>=0.27,<1\npython-dotenv>=1,<2\nPillow>=11,<13\n";
const entries = [
  ...files.map(([name, path]) => ({ name, data: readFileSync(path) })),
  { name: "SETUP.md", data: Buffer.from(setup) },
  { name: "requirements-mcp.txt", data: Buffer.from(requirements) },
];

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let value = n;
  for (let i = 0; i < 8; i++) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});

function crc32(data) {
  let crc = 0xffffffff;
  for (const byte of data) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function zip(entriesToWrite) {
  const local = [];
  const central = [];
  let offset = 0;
  for (const { name, data } of entriesToWrite) {
    const filename = Buffer.from(name);
    const compressed = deflateRawSync(data);
    const checksum = crc32(data);
    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50, 0);
    header.writeUInt16LE(20, 4);
    header.writeUInt16LE(0x0800, 6);
    header.writeUInt16LE(8, 8);
    header.writeUInt32LE(checksum, 14);
    header.writeUInt32LE(compressed.length, 18);
    header.writeUInt32LE(data.length, 22);
    header.writeUInt16LE(filename.length, 26);
    local.push(header, filename, compressed);

    const directory = Buffer.alloc(46);
    directory.writeUInt32LE(0x02014b50, 0);
    directory.writeUInt16LE(20, 4);
    directory.writeUInt16LE(20, 6);
    directory.writeUInt16LE(0x0800, 8);
    directory.writeUInt16LE(8, 10);
    directory.writeUInt32LE(checksum, 16);
    directory.writeUInt32LE(compressed.length, 20);
    directory.writeUInt32LE(data.length, 24);
    directory.writeUInt16LE(filename.length, 28);
    directory.writeUInt32LE(offset, 42);
    central.push(directory, filename);
    offset += header.length + filename.length + compressed.length;
  }
  const centralSize = central.reduce((size, part) => size + part.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entriesToWrite.length, 8);
  end.writeUInt16LE(entriesToWrite.length, 10);
  end.writeUInt32LE(centralSize, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, ...central, end]);
}

mkdirSync(outputRoot, { recursive: true });
writeFileSync(resolve(outputRoot, "video-generation-agent-kit.zip"), zip(entries));
writeFileSync(resolve(outputRoot, "AGENT_PROMPT.md"), readFileSync(resolve(skillRoot, "assets", "AGENT_PROMPT.md")));
console.log("Packaged Video Generation MCP client, skill, and agent prompt.");
