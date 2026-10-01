import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div style={{ background: "#fff", border: "1px solid #d6dfdb", borderRadius: 6, padding: "8px 10px", fontSize: 12 }}>
      <b>Store {r.store_nbr}</b>, {r.city} (type {r.type})<br />
      {fmt.int(r.sales)} units sold<br />
      {r.low_stock} low stock, {r.overstock} overstock
    </div>
  );
}

export default function StoreChart({ store, onStore }) {
  const { data, error, loading } = useApi(() => api.storeAnalytics(), []);
  const rows = data?.slice(0, 20) || [];
  return (
    <section className="panel">
      <h3>Top 20 stores by sales</h3>
      <p className="note">Last 28 days. Red bars have 8 or more lines about to run out. Click a bar to filter the page.</p>
      <Status loading={loading} error={error}>
        <div style={{ height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#e6ece9" vertical={false} />
              <XAxis dataKey="store_nbr" tick={{ fontSize: 11, fill: "#5c6e68" }} interval={0} />
              <YAxis tickFormatter={fmt.compact} tick={{ fontSize: 11, fill: "#5c6e68" }} width={48} />
              <Tooltip content={<Tip />} cursor={{ fill: "#eef2f0" }} />
              <Bar dataKey="sales" radius={[3, 3, 0, 0]} cursor="pointer" onClick={(r) => onStore(store === r.store_nbr ? null : r.store_nbr)}>
                {rows.map((r) => (
                  <Cell key={r.store_nbr} fill={r.low_stock >= 8 ? "var(--low)" : "var(--ink)"} fillOpacity={store && store !== r.store_nbr ? 0.3 : 1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Status>
    </section>
  );
}
