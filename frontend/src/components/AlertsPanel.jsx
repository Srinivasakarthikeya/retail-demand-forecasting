import { STATUS, api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function AlertsPanel({ onPick }) {
  const { data, error, loading } = useApi(() => api.alerts(6), []);
  return (
    <section className="panel">
      <h3>Act on these first</h3>
      <p className="note">Click an item to plan it in the scenario panel.</p>
      <Status loading={loading} error={error}>
        {data && (
          <>
            <div className="alert-group">
              <h4><i className="dot" style={{ background: STATUS.LOW_STOCK.color }} />Runs out before delivery</h4>
              {!data.low_stock.length && <p className="empty" style={{ padding: "4px 0" }}>Every line is covered until the next delivery.</p>}
              {data.low_stock.map((r) => (
                <button key={`${r.store_nbr}-${r.family}`} className="alert-row" onClick={() => onPick(r)}>
                  <span className="what">{fmt.title(r.family)} <small>store {r.store_nbr}</small></span>
                  <span className="how" style={{ color: "var(--low)" }}>short {fmt.compact(r.shortfall_before_delivery)}</span>
                </button>
              ))}
            </div>
            <div className="alert-group">
              <h4><i className="dot" style={{ background: STATUS.OVERSTOCK.color }} />Too much on hand</h4>
              {!data.overstock.length && <p className="empty" style={{ padding: "4px 0" }}>Nothing is overstocked.</p>}
              {data.overstock.map((r) => (
                <button key={`${r.store_nbr}-${r.family}`} className="alert-row" onClick={() => onPick(r)}>
                  <span className="what">{fmt.title(r.family)} <small>store {r.store_nbr}</small></span>
                  <span className="how" style={{ color: "var(--over)" }}>{fmt.days(r.days_cover)} of stock</span>
                </button>
              ))}
            </div>
          </>
        )}
      </Status>
    </section>
  );
}
