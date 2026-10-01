import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

/** Donut with a centred label and a legend list on the right. */
export default function Donut({ rows, valueKey, labelKey, colors, center, sub, formatValue }) {
  return (
    <div className="donut">
      <div className="donut-chart">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={rows} dataKey={valueKey} nameKey={labelKey} innerRadius="62%" outerRadius="98%" paddingAngle={1} stroke="none" startAngle={90} endAngle={-270}>
              {rows.map((r, i) => <Cell key={r[labelKey]} fill={colors[i % colors.length]} />)}
            </Pie>
            <Tooltip formatter={(v) => formatValue(v)} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center"><b>{center}</b><span>{sub}</span></div>
      </div>
      <ul className="legend">
        {rows.map((r, i) => (
          <li key={r[labelKey]}>
            <i className="dot" style={{ background: colors[i % colors.length] }} />
            <span>{r.legend ?? r[labelKey]}</span>
            <b>{Math.round(r.share_pct)}%</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
