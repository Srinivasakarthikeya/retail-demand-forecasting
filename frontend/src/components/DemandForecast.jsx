import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function DemandForecast({ store, family }) {
  const { data, error, loading } = useApi(() => api.forecasts({ store_nbr: store, family, history_days: 14 }), [store, family]);
  const rows = data
    ? [
        ...data.actual.map((r) => ({ date: r.date, units: r.value, kind: "hist" })),
        ...data.forecast.map((r) => ({ date: r.date, units: r.value, kind: "fc" })),
      ]
    : [];
  return (
    <section className="card panel" id="forecasting">
      <div className="panel-head">
        <h2>Demand Forecasting</h2>
        <span className="pill">Next 16 days</span>
      </div>
      <div className="panel-tools" style={{ marginBottom: 6 }}>
        <span className="key"><i className="dot" style={{ background: "#f6b3b6" }} />Historical Demand</span>
        <span className="key"><i className="dot" style={{ background: "#e3141f" }} />Forecasted Demand</span>
      </div>
      <Status loading={loading} error={error}>
        <div style={{ height: 190 }}>
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="#eef0f3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => fmt.date(d, { day: "numeric", month: "short" })} tick={{ fontSize: 11, fill: "#5d6672" }} minTickGap={20} />
              <YAxis tickFormatter={(v) => fmt.short(v, 1)} tick={{ fontSize: 11, fill: "#5d6672" }} width={52} />
              <Tooltip formatter={(v) => [`${fmt.int(v)} units`, "Demand"]} labelFormatter={(d) => fmt.date(d)} cursor={{ fill: "#f6f7f9" }} />
              <Bar dataKey="units" radius={[3, 3, 0, 0]}>
                {rows.map((r) => <Cell key={r.date} fill={r.kind === "fc" ? "#e3141f" : "#f6b3b6"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Status>
    </section>
  );
}
