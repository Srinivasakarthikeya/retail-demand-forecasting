import { ArrowDown, ArrowUp } from "lucide-react";
import { PALETTE, api, fmt } from "../api";
import { Status, useApi } from "./useApi";

const DEPT_COLOR = {};
export default function TopProducts({ onFamily }) {
  const { data, error, loading } = useApi(() => api.families28(), []);
  const depts = [...new Set((data || []).map((r) => r.department))];
  depts.forEach((d, i) => { DEPT_COLOR[d] = PALETTE[i % PALETTE.length]; });

  return (
    <section className="card panel">
      <div className="panel-head">
        <h2>Top Selling Products</h2>
        <a className="view-all" href="#stores">View All</a>
      </div>
      <Status loading={loading} error={error}>
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>#</th><th>Product family</th><th>Department</th><th className="num">Sales</th><th className="num">Growth</th></tr></thead>
          <tbody>
            {data?.slice(0, 5).map((r, i) => {
              const up = (r.growth_pct ?? 0) >= 0;
              return (
                <tr key={r.family} className="clickable" onClick={() => onFamily(r.family)}>
                  <td>{i + 1}</td>
                  <td>
                    <span className="thumb" style={{ background: `${DEPT_COLOR[r.department]}1a`, color: DEPT_COLOR[r.department] }}>
                      {r.family.slice(0, 2)}
                    </span>
                    {fmt.title(r.family)}
                  </td>
                  <td className="wrap muted">{r.department}</td>
                  <td className="num">{fmt.inr(r.sales_inr)}</td>
                  <td className={`num ${up ? "pos" : "neg"}`}>
                    {r.growth_pct == null ? "–" : <>{up ? <ArrowUp size={14} strokeWidth={2.5} /> : <ArrowDown size={14} strokeWidth={2.5} />}{fmt.pct(r.growth_pct)}</>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table></div>
      </Status>
    </section>
  );
}
