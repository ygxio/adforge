// Run a shell script inside the shared "adbox" sandbox, streaming output.
// Usage: node --env-file=.env scripts/sb.mjs '<bash script>'
import { CreateosSandboxClient } from "@nodeops-createos/sandbox";

const client = new CreateosSandboxClient();
const NAME = "adbox";

async function getBox() {
  const all = await client.listSandboxes();
  let box = all.find((s) => s.name === NAME && s.status !== "destroyed");
  if (box) {
    if (box.status === "paused") await box.resume();
    return box;
  }
  return client.createSandbox({
    shape: "s-2vcpu-2gb",
    rootfs: "devbox:1",
    name: NAME,
    auto_pause_after_seconds: 900,
  });
}

const box = await getBox();
console.error(`[sandbox ${box.id} ${box.status}]`);
let code = 0;
for await (const ev of box.streamCommand("bash", ["-lc", process.argv[2]], { timeoutMs: 1_800_000 })) {
  if (ev.type === "stdout") process.stdout.write(ev.data);
  else if (ev.type === "stderr") process.stderr.write(ev.data);
  else if (ev.type === "exit") code = ev.exitCode;
  else if (ev.type === "error") { console.error("ERR", ev.message); code = 1; }
}
process.exit(code);
