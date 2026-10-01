import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

const RANGES = { "Last 8 weeks": 56, "Last 3 months": 91, "Last 6 months": 182 };

/** Average daily value per week (Mon-Sun): partial first/last weeks stay comparable. */
function weekly(list) {
  const sum = new Map(), n = new Map();
  for (const { date, value } of list) {
    const d = new Date(date);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const k = d.toISOString().slice(0, 10);
    sum.set(k, (sum.get(k) || 0) + value);
    n.set(k, (n.get(k) || 0) + 1);
  }
  return new Map([...sum].map(([k, v]) => [k, v / n.get(k)]));
}

export default function SalesTrend({ store, family }) {
  const [range, setRange] = useState("Last 3 months");
  const { data, error, loading } = useApi(
    () => api.forecasts({ store_nbr: store, family, history_days: RANGES[range], metric: "inr" }),
    [store, family, range],
  );

  let rows = [];
  if (data) {
    const a = weekly(data.actual);
    const p = weekly([...data.backtest, ...data.forecast]);
    rows = [...new Set([...a.keys(), ...p.keys()])].sort().map((k) => ({ week: k, actual: a.get(k), predicted: p.get(k) }));
  }

  return (
    <section className="card panel" id="sales">
      <div className="panel-head">
        <h2>Sales Trend <small className="muted">avg per day</small></h2>
        <div className="panel-tools">
          <span className="key"><i className="dot" style={{ background: "#e3141f" }} />Actual Sales</span>
          <span className="key"><i className="dash" />Predicted Sales</span>
          <select value={range} onChange={(e) => setRange(e.target.value)} aria-label="Range">
            {Object.keys(RANGES).map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
      </div>
      <Status loading={loading} error={error} empty={data && !rows.length ? "No sales for this selection." : null}>
        <div style={{ height: 230 }}>
          <ResponsiveContainer>
            <ComposedChart data={rows} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="redfill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#e3141f" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#e3141f" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#eef0f3" />
              <XAxis dataKey="week" tickFormatter={(d) => fmt.date(d, { day: "numeric", month: "short" })} tick={{ fontSize: 12, fill: "#5d6672" }} minTickGap={28} />
              <YAxis tickFormatter={(v) => fmt.inr(v, 1)} tick={{ fontSize: 12, fill: "#5d6672" }} width={70} />
              <Tooltip formatter={(v, n) => [`${fmt.inr(v)} / day`, n]} labelFormatter={(d) => `Week of ${fmt.date(d)}`} />
              <Area type="monotone" dataKey="actual" name="Actual" stroke="#e3141f" strokeWidth={2.5} fill="url(#redfill)" dot={{ r: 4, fill: "#e3141f", strokeWidth: 0 }} />
              <Line type="monotone" dataKey="predicted" name="Predicted" stroke="#f28b91" strokeWidth={2} strokeDasharray="6 5" dot={{ r: 4, fill: "#f28b91", strokeWidth: 0 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Status>
    </section>
  );
}
