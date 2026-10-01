import { STATUS, api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function InventoryAlerts({ onPick }) {
  const { data, error, loading } = useApi(() => api.alerts(4), []);
  const rows = data
    ? [
        ...data.low_stock.map((r) => ({ ...r, kind: r.on_hand <= 0 ? "OUT" : "LOW_STOCK", action: `Reorder ${fmt.short(r.order_qty)} units` })),
        ...data.overstock.slice(0, 1).map((r) => ({ ...r, kind: "OVERSTOCK", action: "Reduce purchase" })),
      ]
    : [];
  return (
    <section className="card panel">
      <div className="panel-head">
        <h2>Inventory Alerts</h2>
        <a className="view-all" href="#inventory">View All</a>
      </div>
      <Status loading={loading} error={error} empty={data && !rows.length ? "No stock alerts today." : null}>
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>Product</th><th className="num">Current Stock</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.store_nbr}-${r.family}`} className="clickable" onClick={() => onPick(r)}>
                <td className="wrap">{fmt.title(r.family)} <small className="muted">Store {r.store_nbr}</small></td>
                <td className={`num ${r.kind === "OUT" ? "neg" : ""}`}>{fmt.int(r.on_hand)}</td>
                <td><span className={`badge ${STATUS[r.kind].cls}`}>{STATUS[r.kind].short}</span></td>
                <td>{r.action}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Status>
    </section>
  );
}
