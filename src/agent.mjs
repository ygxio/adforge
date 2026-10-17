// The AdForge agent loop: write Blender code -> run in CreateOS sandbox -> read
// errors / look at the draft -> rewrite -> final render -> composite Stripe QR.
import { mkdir, writeFile } from "node:fs/promises";
import { chat, imagePart, extractPython, MODEL } from "./llm.mjs";
import { getBox, sh } from "./sandbox.mjs";
import { resolveProduct, paymentLink } from "./stripe.mjs";
import { SYSTEM, userBrief, CRITIC } from "./prompts.mjs";

const MAX_FIX_ATTEMPTS = 4;
const MAX_CRITIQUES = Number(process.env.MAX_CRITIQUES ?? 1);
const PRELUDE = "import sys\nsys.path.insert(0, '/opt/adkit')\n";

// One sandbox on the free plan, so jobs run one at a time.
let queue = Promise.resolve();
export const enqueue = (fn) => (queue = queue.then(fn, fn));

function blenderCmd(dir, { res, samples, frames }) {
  const env = [`AD_OUT=${dir}/out/ad.png`, `AD_FRAMES=${dir}/out/frames`];
  if (res) env.push(`AD_RES=${res}`);
  if (samples) env.push(`AD_SAMPLES=${samples}`);
  if (frames) env.push(`AD_FRAMES_N=${frames}`);
  // Drop Blender's per-tile noise but keep sample progress, errors and our markers.
  return `cd ${dir} && rm -rf out && ${env.join(" ")} blender -b --python-exit-code 1 -P scene.py 2>&1 | grep -E --line-buffered "Error|error:|Traceback|File \\"|^\\s|Sample [0-9]+/|ADKIT|Saved|Fra:[0-9]+ .*Rendering 1 /" | grep -v "Remaining" ; exit \${PIPESTATUS[0]}`;
}

export async function runJob(input, emit) {
  const id = input.id;
  const dir = `/work/${id}`;
  const local = new URL(`../out/${id}/`, import.meta.url);
  await mkdir(local, { recursive: true });
  const log = (msg) => emit({ type: "log", msg });
  const step = (name) => emit({ type: "step", step: name });

  // 1. Stripe: product + Payment Link
  step("stripe");
  const product = await resolveProduct(input);
  log(`Product: ${product.name} ${product.price}`);
  let link = null;
  try {
    link = await paymentLink(product.priceId);
    log(link ? `Payment Link: ${link.url}` : "No STRIPE_SECRET_KEY: skipping Payment Link + QR");
  } catch (e) {
    log(`Payment Link failed (${e.message.slice(0, 120)}), shipping ad without QR`);
  }

  // 2. Sandbox + assets
  step("sandbox");
  const box = await getBox(log);
  await sh(box, `mkdir -p ${dir}/assets`);
  if (link) await box.files.upload(`${dir}/assets/qr.png`, link.qr);
  const imageUrl = input.imageUrl || product.image;
  let hasImage = false;
  if (imageUrl) {
    const r = await sh(box, `curl -sSfL --max-time 20 -o ${dir}/assets/raw "${imageUrl}" && ffmpeg -loglevel error -y -i ${dir}/assets/raw ${dir}/assets/product.png && echo OK`);
    hasImage = r.code === 0;
    log(hasImage ? "Product image loaded into sandbox" : "Could not fetch product image, continuing without it");
  }
  const job = { ...input, ...product, hasImage };

  // 3. Write -> run -> fix loop, with a cheap draft render the critic can look at.
  const messages = [{ role: "system", content: SYSTEM }, { role: "user", content: userBrief(job) }];
  let code = null;
  let critiques = 0;
  let draftOk = false;
  for (let attempt = 1; attempt <= MAX_FIX_ATTEMPTS + MAX_CRITIQUES; attempt++) {
    step("write");
    log(`${MODEL} writing scene script (attempt ${attempt})`);
    const reply = await chat(messages);
    messages.push({ role: "assistant", content: reply });
    code = extractPython(reply);
    emit({ type: "code", code, attempt });

    step("draft");
    await box.files.upload(`${dir}/scene.py`, PRELUDE + code);
    log("Draft render in sandbox (540p)");
    const t = Date.now();
    const run = await sh(box, blenderCmd(dir, { res: 540, samples: 12, frames: 1 }), (l) => emit({ type: "sandbox", line: l }));
    const produced = run.code === 0 && /ADKIT_(RENDERED|FRAMES)/.test(run.out);
    if (!produced) {
      const tail = run.out.split("\n").slice(-40).join("\n");
      log(`Script failed (exit ${run.code}); feeding error back to the model`);
      emit({ type: "error_trace", text: tail });
      messages.push({ role: "user", content: `The script failed in Blender. Output tail:\n${tail}\nFix it and return the full corrected script.` });
      continue;
    }
    log(`Draft rendered in ${((Date.now() - t) / 1000).toFixed(1)}s`);
    const draftPath = input.animate ? `${dir}/out/frames/f_0001.png` : `${dir}/out/ad.png`;
    const draft = Buffer.from(await box.files.download(draftPath));
    await writeFile(new URL(`draft${attempt}.png`, local), draft);
    emit({ type: "image", label: `Draft ${attempt}`, url: `/out/${id}/draft${attempt}.png` });
    draftOk = true;

    if (critiques >= MAX_CRITIQUES) break;
    step("critique");
    critiques++;
    log("Art director (vision) reviewing the draft");
    const review = JSON.parse(await chat([
      { role: "system", content: CRITIC },
      { role: "user", content: [{ type: "text", text: `Brief:\n${userBrief(job)}` }, imagePart(draft)] },
    ], { json: true, temperature: 0.2 }));
    emit({ type: "critique", ...review });
    if (review.score >= 8) break;
    messages.push({
      role: "user",
      content: [
        { type: "text", text: `Art director feedback (score ${review.score}/10): ${review.issues?.join("; ")}\nFix: ${review.fix}\nHere is your draft. Return the full improved script.` },
        imagePart(draft),
      ],
    });
  }
  if (!draftOk) throw new Error("Could not produce a working scene script");

  // 4. Final quality render + QR composite (ffmpeg inside the sandbox).
  step("render");
  const animate = Boolean(input.animate);
  log(animate ? "Final animation render (48 frames, 540p)" : "Final render (1080p)");
  const t = Date.now();
  const fin = await sh(box, blenderCmd(dir, animate ? { res: 540, samples: 16 } : { res: 1080, samples: 32 }),
    (l) => emit({ type: "sandbox", line: l }));
  if (fin.code !== 0) throw new Error("Final render failed");
  log(`Final render done in ${((Date.now() - t) / 1000).toFixed(0)}s`);

  step("composite");
  const overlay = link
    ? `-i ${dir}/assets/qr.png -filter_complex "[1][0]scale2ref=w=ih*0.17:h=ih*0.17[qr][bg];[bg][qr]overlay=W-w-W*0.04:H-h-H*0.075,drawtext=fontfile=/opt/fonts/Poppins-Bold.ttf:text='SCAN TO BUY':fontcolor=white:fontsize=h*0.024:x=W-W*0.04-h*0.085-tw/2:y=H-H*0.06"`
    : "";
  const files = { image: null, video: null, gif: null };
  if (animate) {
    const r = await sh(box, `cd ${dir}/out && ffmpeg -loglevel error -y -framerate 24 -i frames/f_%04d.png ${overlay} -c:v libx264 -pix_fmt yuv420p -crf 20 ad.mp4 && ffmpeg -loglevel error -y -i ad.mp4 -vf "fps=15,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" ad.gif && cp frames/f_0001.png ad.png && echo OK`);
    if (r.code !== 0) throw new Error(`Video encode failed: ${r.out.slice(-300)}`);
    for (const f of ["ad.mp4", "ad.gif"]) await writeFile(new URL(f, local), Buffer.from(await box.files.download(`${dir}/out/${f}`)));
    files.video = `/out/${id}/ad.mp4`;
    files.gif = `/out/${id}/ad.gif`;
  }
  if (overlay) {
    const r = await sh(box, `cd ${dir}/out && ffmpeg -loglevel error -y -i ad.png ${overlay} final.png && echo OK`);
    if (r.code !== 0) throw new Error(`Composite failed: ${r.out.slice(-300)}`);
  } else {
    await sh(box, `cp ${dir}/out/ad.png ${dir}/out/final.png`);
  }
  await writeFile(new URL("final.png", local), Buffer.from(await box.files.download(`${dir}/out/final.png`)));
  await writeFile(new URL("scene.py", local), code);
  files.image = `/out/${id}/final.png`;
  await sh(box, `rm -rf ${dir}/out/frames`);

  emit({ type: "done", ...files, link: link?.url || null, product, code });
}
