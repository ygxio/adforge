// Host AdForge inside its own CreateOS sandbox and expose it with HTTP ingress.
// The app then drives Blender in the same sandbox it is served from.
// Usage: node --env-file=.env scripts/deploy.mjs
import { CreateosSandboxClient } from "@nodeops-createos/sandbox";
import { readFile } from "node:fs/promises";

const FILES = ["package.json", "package-lock.json", "src/agent.mjs", "src/llm.mjs", "src/prompts.mjs", "src/sandbox.mjs",
  "src/server.mjs", "src/stripe.mjs", "sandbox/adkit.py", "public/index.html", ".env"];

const client = new CreateosSandboxClient();
const box = (await client.listSandboxes()).find((s) => s.name === (process.env.SANDBOX_NAME || "adbox"));
if (!box) throw new Error("sandbox not found");

for (const f of FILES) await box.files.upload(`/app/${f}`, await readFile(f));
console.log("uploaded app");

await box.setIngress(true);
// A hosted site must not pause when nobody is generating.
if (box.setAutoPause) await box.setAutoPause(null).catch((e) => console.log("auto-pause:", e.message));

const r = await box.runCommand("bash", ["-lc", `cd /app && npm ci --omit=dev --silent >/dev/null 2>&1 && \
  (pkill -f "node src/server.mj[s]" || true) && \
  (PORT=3000 nohup node --env-file=.env src/server.mjs > /app/server.log 2>&1 &) && sleep 4 && \
  curl -s -o /dev/null -w "%{http_code}" localhost:3000/`], { timeoutMs: 300_000 });
console.log("local status:", r.result.stdout, r.result.stderr.slice(-300));
console.log("LIVE:", box.previewUrl(3000));
