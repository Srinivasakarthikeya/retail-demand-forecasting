import { STATUS, api, fmt } from "../api";
import { Status, useApi } from "./useApi";

const FILTERS = [null, "LOW_STOCK", "REORDER", "OVERSTOCK", "OK"];

export default function ReorderTable({ store, family, status, onStatus, selected, onPick, counts }) {
  const { data, error, loading } = useApi(
    () => api.recommendations({ store_nbr: store, family, status, limit: 300 }),
    [store, family, status],
  );
  const isSel = (r) => selected && selected.store_nbr === r.store_nbr && selected.family === r.family;

  return (
    <section className="card panel" id="inventory">
      <div className="panel-head">
        <h2>Order List</h2>
        <div className="chips" role="group" aria-label="Status filter">
          {FILTERS.map((s) => (
            <button key={s || "all"} className="chip" aria-pressed={status === s} onClick={() => onStatus(s)}>
              {s ? STATUS[s].short : "All"}{s && counts ? ` (${fmt.int(counts[s])})` : ""}
            </button>
          ))}
        </div>
      </div>
      <p className="muted small">Largest orders first. Each order covers the next 10 days plus safety stock. Click a row to plan it.</p>
      <Status loading={loading} error={error} empty={data && !data.length ? "Nothing matches these filters." : null}>
        <div className="table-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Product family</th><th>Store</th><th>Status</th><th className="num">On hand</th>
                <th className="num">Next 10 days</th><th className="num">Cover</th><th className="num">Order</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((r) => {
                const kind = r.status === "LOW_STOCK" && r.on_hand <= 0 ? "OUT" : r.status;
                return (
                  <tr key={`${r.store_nbr}-${r.family}`} className={`clickable${isSel(r) ? " selected" : ""}`} onClick={() => onPick(r)}>
                    <td>{fmt.title(r.family)}</td>
                    <td>{r.store_nbr}</td>
                    <td><span className={`badge ${STATUS[kind].cls}`}>{STATUS[kind].short}</span></td>
                    <td className="num">{fmt.int(r.on_hand)}</td>
                    <td className="num">{fmt.int(r.forecast_10d)}</td>
                    <td className="num">{fmt.days(r.days_cover)}</td>
                    <td className="num"><b>{fmt.int(r.order_qty)}</b></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Status>
    </section>
  );
}
