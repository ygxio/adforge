// Stripe: product catalog in, Payment Link + QR code out.
import Stripe from "stripe";
import QRCode from "qrcode";

const key = process.env.STRIPE_SECRET_KEY;
export const stripe = key ? new Stripe(key) : null;

const money = (amount, currency) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase(), minimumFractionDigits: amount % 100 ? 2 : 0 })
    .format(amount / 100);

export async function listProducts() {
  if (!stripe) return [];
  const prices = await stripe.prices.list({ active: true, limit: 50, expand: ["data.product"] });
  return prices.data
    .filter((p) => p.product?.active && p.unit_amount)
    .map((p) => ({
      priceId: p.id,
      productId: p.product.id,
      name: p.product.name,
      description: p.product.description || "",
      image: p.product.images?.[0] || null,
      price: money(p.unit_amount, p.currency),
    }));
}

// Use an existing price, or create the product + price from the form input.
export async function resolveProduct({ priceId, name, description, price }) {
  if (!stripe || (!priceId && !(parseFloat(String(price).replace(/[^0-9.]/g, "")) > 0))) {
    return { name, description, price: price ? `$${price}` : "", image: null, priceId: null };
  }
  if (priceId) {
    const p = await stripe.prices.retrieve(priceId, { expand: ["product"] });
    return { priceId, name: p.product.name, description: p.product.description || "", image: p.product.images?.[0] || null, price: money(p.unit_amount, p.currency) };
  }
  const amount = Math.round(parseFloat(String(price).replace(/[^0-9.]/g, "")) * 100);
  const product = await stripe.products.create({ name, ...(description && { description }), metadata: { source: "adforge" } });
  const p = await stripe.prices.create({ product: product.id, unit_amount: amount, currency: "usd" });
  return { priceId: p.id, name, description, image: null, price: money(amount, "usd") };
}

export async function paymentLink(priceId) {
  if (!stripe || !priceId) return null;
  const link = await stripe.paymentLinks.create({
    line_items: [{ price: priceId, quantity: 1 }],
    metadata: { source: "adforge" },
  });
  const qr = await QRCode.toBuffer(link.url, { width: 360, margin: 2, color: { dark: "#000000", light: "#ffffff" } });
  return { url: link.url, qr };
}
