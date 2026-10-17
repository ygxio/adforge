import http from "node:http";
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { extname, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { runJob, enqueue } from "./agent.mjs";
import { listProducts } from "./stripe.mjs";
import { getBox } from "./sandbox.mjs";

const PORT = Number(process.env.PORT || 3000);
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const TYPES = { ".html": "text/html", ".png": "image/png", ".mp4": "video/mp4", ".gif": "image/gif", ".py": "text/plain", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" };

const jobs = new Map(); // id -> { events: [], listeners: Set, done }

function emitter(job) {
  return (ev) => {
    ev.t = Date.now();
    job.events.push(ev);
    for (const res of job.listeners) res.write(`data: ${JSON.stringify(ev)}\n\n`);
  };
}

const body = (req) => new Promise((ok, fail) => {
  let s = "";
  req.on("data", (c) => (s += c));
  req.on("end", () => { try { ok(s ? JSON.parse(s) : {}); } catch (e) { fail(e); } });
});

const json = (res, code, data) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(data)); };

async function serveFile(res, path) {
  try {
    const data = await readFile(path);
    res.writeHead(200, { "Content-Type": TYPES[extname(path)] || "application/octet-stream" });
    res.end(data);
  } catch {
    res.writeHead(404); res.end("not found");
  }
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  try {
    if (req.method === "GET" && url.pathname === "/") return serveFile(res, `${ROOT}public/index.html`);
    if (req.method === "GET" && url.pathname === "/api/products") return json(res, 200, await listProducts());

    if (req.method === "POST" && url.pathname === "/api/jobs") {
      const input = await body(req);
      if (!input.priceId && !input.name) return json(res, 400, { error: "name or priceId required" });
      const id = randomUUID().slice(0, 8);
      const job = { events: [], listeners: new Set(), done: false };
      jobs.set(id, job);
      const emit = emitter(job);
      emit({ type: "log", msg: "Queued" });
      enqueue(() => runJob({ ...input, id }, emit)
        .catch((e) => emit({ type: "error", msg: e.message }))
        .finally(() => { job.done = true; for (const r of job.listeners) r.end(); }));
      return json(res, 200, { id });
    }

    const m = url.pathname.match(/^\/api\/jobs\/([\w-]+)\/events$/);
    if (req.method === "GET" && m) {
      const job = jobs.get(m[1]);
      if (!job) return json(res, 404, { error: "no such job" });
      res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
      for (const ev of job.events) res.write(`data: ${JSON.stringify(ev)}\n\n`);
      if (job.done) return res.end();
      job.listeners.add(res);
      req.on("close", () => job.listeners.delete(res));
      return;
    }

    if (req.method === "GET" && (url.pathname.startsWith("/out/") || url.pathname.startsWith("/static/"))) {
      const p = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, "");
      const base = p.startsWith("/out/") ? ROOT : `${ROOT}public`;
      return serveFile(res, base + p.replace(/^\/static/, ""));
    }
    res.writeHead(404); res.end("not found");
  } catch (e) {
    console.error(e);
    json(res, 500, { error: e.message });
  }
}).listen(PORT, () => {
  console.log(`AdForge on http://localhost:${PORT}`);
  // Warm the sandbox so the first ad doesn't wait on Blender install.
  getBox((m) => console.log("[sandbox]", m)).catch((e) => console.error("[sandbox]", e.message));
});
