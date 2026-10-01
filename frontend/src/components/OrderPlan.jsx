import { STATUS, fmt } from "../api";

const ORDER = ["LOW_STOCK", "REORDER", "OVERSTOCK", "OK"];

export default function OrderPlan({ kpis, status, onStatus }) {
  const total = ORDER.reduce((s, k) => s + (kpis.alerts[k] || 0), 0);
  const ml = kpis.forecast_backtest?.LightGBM;
  const base = kpis.forecast_backtest?.["28-day moving avg (baseline)"];
  const sim = kpis.policy_simulation?.["z1.645_lost_sales_vs_textbook_equal_inventory_%"];
  const runDate = new Date(kpis.recommendation_run).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const change = kpis.sales_change_pct;

  return (
    <section className="plan" aria-labelledby="plan-title">
      <div className="plan-head">
        <div>
          <h2 id="plan-title">Order {fmt.compact(kpis.units_to_order)} units this week</h2>
          <p className="plan-sub">
            Plan for {runDate}. {fmt.int(kpis.alerts.LOW_STOCK)} store–product lines will run out before the next
            delivery arrives, and {fmt.int(kpis.alerts.OVERSTOCK)} are holding more than three weeks of stock.
          </p>
        </div>
        <div className="plan-figures">
          <div className="figure">
            <b>{fmt.compact(kpis.sales_last_28d)}</b>
            <span>
              units sold, 28 days{" "}
              {change != null && <em className={change >= 0 ? "up" : "down"}>{fmt.pct(change)}</em>}
            </span>
          </div>
          {ml && base && (
            <div className="figure">
              <b>{ml["WAPE_%"].toFixed(1)}%</b>
              <span>forecast error, vs {base["WAPE_%"].toFixed(1)}% before</span>
            </div>
          )}
          {sim != null && (
            <div className="figure">
              <b>{Math.round(sim)}%</b>
              <span>fewer lost sales in a 12-month simulation</span>
            </div>
          )}
        </div>
      </div>

      <div className="shelf" role="group" aria-label="Filter the order table by status">
        {ORDER.map((k) => {
          const n = kpis.alerts[k] || 0;
          if (!n) return null;
          return (
            <button
              key={k}
              style={{ flexGrow: n, background: STATUS[k].color }}
              aria-pressed={status === k}
              onClick={() => onStatus(status === k ? null : k)}
              title={`${STATUS[k].label}: ${fmt.int(n)}`}
            >
              {fmt.int(n)}
            </button>
          );
        })}
      </div>
      <div className="shelf-legend">
        {ORDER.map((k) => (
          <span key={k}>
            <i className="dot" style={{ background: STATUS[k].color }} />
            {STATUS[k].label} ({Math.round((100 * (kpis.alerts[k] || 0)) / total)}%)
          </span>
        ))}
      </div>
    </section>
  );
}
