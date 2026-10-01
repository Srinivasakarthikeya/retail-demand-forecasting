import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function ForecastChart({ store, family }) {
  const { data, error, loading } = useApi(
    () => api.forecasts({ store_nbr: store, family, history_days: 60 }),
    [store, family],
  );

  let rows = [];
  let lastActual = null;
  if (data) {
    const byDate = new Map();
    const put = (list, key) => list.forEach((r) => byDate.set(r.date, { ...(byDate.get(r.date) || { date: r.date }), [key]: r.value }));
    put(data.actual, "actual");
    put(data.backtest, "backtest");
    put(data.forecast, "forecast");
    rows = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
    lastActual = data.actual.at(-1)?.date;
  }
  const scope = [store ? `store ${store}` : "all stores", family ? fmt.title(family) : "all products"].join(", ");

  return (
    <section className="panel">
      <h3>Daily demand and 16-day forecast</h3>
      <p className="note">Units per day for {scope}. The dashed line is what the model predicted for days we already know.</p>
      <Status loading={loading} error={error} empty={data && !rows.length ? "No sales for this selection." : null}>
        <div style={{ height: 320 }}>
          <ResponsiveContainer>
            <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#e6ece9" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 11, fill: "#5c6e68" }} minTickGap={24} />
              <YAxis tickFormatter={fmt.compact} tick={{ fontSize: 11, fill: "#5c6e68" }} width={48} />
              <Tooltip formatter={(v, n) => [fmt.int(v), n]} labelStyle={{ fontWeight: 600 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="actual" name="Actual" stroke="var(--actual)" fill="#dfe6e3" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="backtest" name="Model on known days" stroke="var(--ink)" strokeDasharray="5 4" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke="var(--ink)" strokeWidth={2.5} dot={false} />
              {lastActual && <ReferenceLine x={lastActual} stroke="var(--reorder)" label={{ value: "today", position: "insideTopRight", fontSize: 11, fill: "#c28a1a" }} />}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Status>
    </section>
  );
}
