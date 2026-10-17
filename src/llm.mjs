// Minimal OpenAI-compatible chat client. Uses OpenAI if OPENAI_API_KEY is set,
// otherwise OpenRouter (provisioned through Stripe Projects).

const openai = process.env.OPENAI_API_KEY;
const BASE = openai ? "https://api.openai.com/v1" : "https://openrouter.ai/api/v1";
const KEY = openai || process.env.OPENROUTER_API_KEY;
export const MODEL = process.env.LLM_MODEL || (openai ? "gpt-5.5" : "openai/gpt-5.5");
// Reasoning models (gpt-5*, o*) reject a custom temperature but take an effort level.
const REASONING = /(^|\/)(gpt-[5-9]|o\d)/.test(MODEL);

export async function chat(messages, { json = false, temperature = 0.7 } = {}) {
  if (!KEY) throw new Error("No LLM key: set OPENAI_API_KEY (or OPENROUTER_API_KEY) in .env");
  const res = await fetch(`${BASE}/chat/completions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      messages,
      ...(REASONING ? { reasoning_effort: process.env.LLM_EFFORT || "low" } : { temperature }),
      ...(json && { response_format: { type: "json_object" } }),
    }),
  });
  if (!res.ok) throw new Error(`LLM ${res.status}: ${(await res.text()).slice(0, 400)}`);
  const data = await res.json();
  return data.choices[0].message.content;
}

// Image content part for vision models.
export const imagePart = (png) => ({
  type: "image_url",
  image_url: { url: `data:image/png;base64,${Buffer.from(png).toString("base64")}` },
});

export function extractPython(text) {
  const m = text.match(/```(?:python|py)?\s*\n([\s\S]*?)```/);
  return (m ? m[1] : text).trim();
}
