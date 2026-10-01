const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText} on ${path}`);
  }
  return res.json();
}

const qs = (params) => {
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return p.length ? `?${new URLSearchParams(p)}` : "";
};

export const API_BASE = BASE;
export const api = {
  kpis: () => request("/kpis"),
  stores: () => request("/stores"),
  families: () => request("/families"),
  forecasts: (f) => request(`/forecasts${qs(f)}`),
  alerts: (limit = 8) => request(`/alerts${qs({ limit })}`),
  recommendations: (f) => request(`/recommendations${qs(f)}`),
  families28: () => request("/analytics/families"),
  departments: () => request("/analytics/departments"),
  storeTypes: () => request("/analytics/store-types"),
  spikes: () => request("/analytics/spikes?limit=3"),
  whatif: (body) =>
    request("/whatif", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
};

const IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Indian short scale: 1.2 K, 3.4 L (lakh = 1e5), 5.6 Cr (crore = 1e7). */
function indianShort(n, digits = 2) {
  const a = Math.abs(n);
  if (a >= 1e7) return `${(n / 1e7).toFixed(digits)} Cr`;
  if (a >= 1e5) return `${(n / 1e5).toFixed(digits)} L`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a >= 1e4 ? 0 : 1)} K`;
  return IN.format(n);
}

export const fmt = {
  int: (n) => (n == null ? "–" : IN.format(Math.round(n))),
  short: (n, d) => (n == null ? "–" : indianShort(n, d)),
  inr: (n, d) => (n == null ? "–" : `₹${indianShort(n, d)}`),
  inrFull: (n) => (n == null ? "–" : `₹${IN.format(Math.round(n))}`),
  pct: (n, d = 1) => (n == null ? "–" : `${Math.abs(n).toFixed(d)}%`),
  days: (n) => (n == null ? "–" : n >= 100 ? `${Math.round(n)} d` : `${n.toFixed(1)} d`),
  title: (s) => s.toLowerCase().replace(/(^|[\s/,])\w/g, (m) => m.toUpperCase()),
  date: (d, opts = { day: "numeric", month: "short", year: "numeric" }) => new Date(d).toLocaleDateString("en-IN", opts),
};

export const STATUS = {
  LOW_STOCK: { short: "Low Stock", cls: "badge-red" },
  OUT: { short: "Out of Stock", cls: "badge-red-strong" },
  REORDER: { short: "Reorder", cls: "badge-amber" },
  OVERSTOCK: { short: "Overstock", cls: "badge-yellow" },
  OK: { short: "OK", cls: "badge-green" },
};

export const PALETTE = ["#e3141f", "#2f80ed", "#27ae60", "#f2b632", "#7b4fd6", "#f2994a", "#9aa3ad"];
