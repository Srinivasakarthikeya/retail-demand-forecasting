import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function FamilyTable({ family, onFamily }) {
  const { data, error, loading } = useApi(() => api.familyAnalytics(), []);
  const max = data ? Math.max(...data.map((r) => r.share_pct)) : 1;
  return (
    <section className="panel">
      <h3>Product families</h3>
      <p className="note">Share of sales in the last 28 days, and how much promotions lift each one.</p>
      <Status loading={loading} error={error}>
        <div className="table-wrap" style={{ maxHeight: 300 }}>
          <table>
            <thead><tr><th>Family</th><th>Share of sales</th><th>Promo lift</th><th>Low</th><th>Over</th></tr></thead>
            <tbody>
              {data?.map((r) => (
                <tr key={r.family} aria-selected={family === r.family} onClick={() => onFamily(family === r.family ? null : r.family)}>
                  <td>{fmt.title(r.family)}</td>
                  <td style={{ textAlign: "left" }}>
                    <i className="share" style={{ width: `${Math.max(2, (60 * r.share_pct) / max)}px` }} />
                    {r.share_pct.toFixed(1)}%
                  </td>
                  <td>{r.promo_lift ? `${r.promo_lift}×` : "–"}</td>
                  <td style={{ color: r.low_stock ? "var(--low)" : undefined }}>{r.low_stock}</td>
                  <td style={{ color: r.overstock ? "var(--over)" : undefined }}>{r.overstock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Status>
    </section>
  );
}
