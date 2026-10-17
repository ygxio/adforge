// CreateOS sandbox that runs headless Blender. One long-lived box, reused across
// jobs and auto-paused when idle (the free plan allows one concurrent sandbox).
import { CreateosSandboxClient } from "@nodeops-createos/sandbox";
import { readFile } from "node:fs/promises";

const client = new CreateosSandboxClient();
const NAME = process.env.SANDBOX_NAME || "adbox";
const SHAPE = process.env.SANDBOX_SHAPE || "s-2vcpu-2gb";

const SETUP = `set -e
export DEBIAN_FRONTEND=noninteractive
if ! command -v blender >/dev/null; then
  apt-get update -qq >/dev/null
  apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6 libice6 xz-utils ffmpeg >/dev/null 2>&1
  cd /opt && curl -sSfL https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz | tar -xJ
  ln -sf /opt/blender-4.2.3-linux-x64/blender /usr/local/bin/blender
fi
mkdir -p /opt/fonts /opt/adkit /work && cd /opt/fonts
for f in anton/Anton-Regular.ttf poppins/Poppins-Bold.ttf poppins/Poppins-Regular.ttf bebasneue/BebasNeue-Regular.ttf; do
  [ -f "$(basename $f)" ] || curl -sSfLO https://raw.githubusercontent.com/google/fonts/main/ofl/$f || true
done
echo READY`;

let boxPromise = null;

async function findOrCreate(log) {
  const existing = (await client.listSandboxes()).find((s) => s.name === NAME && s.status !== "destroyed");
  let box = existing;
  if (box?.status === "paused") {
    log(`Resuming sandbox ${box.id}`);
    await box.resume();
  } else if (!box) {
    log(`Creating sandbox (${SHAPE})`);
    box = await client.createSandbox({ shape: SHAPE, rootfs: "devbox:1", name: NAME, auto_pause_after_seconds: 900 });
  }
  log(`Sandbox ${box.id} ready, checking Blender`);
  const r = await box.runCommand("bash", ["-lc", SETUP], { timeoutMs: 900_000 });
  if (r.result.exit_code !== 0) throw new Error(`Sandbox setup failed: ${r.result.stderr.slice(-500)}`);
  await box.files.upload("/opt/adkit/adkit.py", await readFile(new URL("../sandbox/adkit.py", import.meta.url), "utf8"));
  return box;
}

export async function getBox(log = () => {}) {
  if (!boxPromise) boxPromise = findOrCreate(log).catch((e) => { boxPromise = null; throw e; });
  const box = await boxPromise;
  await box.refresh();
  if (box.status === "paused") await box.resume();
  return box;
}

// Run a shell script, streaming each output line to `onLine`.
export async function sh(box, script, onLine = () => {}, timeoutMs = 1_200_000) {
  let code = 0, out = "", buf = "";
  const flush = (s) => {
    buf += s;
    const lines = buf.split("\n");
    buf = lines.pop();
    lines.forEach(onLine);
  };
  for await (const ev of box.streamCommand("bash", ["-lc", script], { timeoutMs })) {
    if (ev.type === "stdout" || ev.type === "stderr") { out += ev.data; flush(ev.data); }
    else if (ev.type === "exit") code = ev.exitCode;
    else if (ev.type === "error") { out += ev.message; code = code || 1; }
  }
  if (buf) onLine(buf);
  return { code, out };
}
