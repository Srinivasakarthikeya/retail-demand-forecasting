import { useEffect, useState } from "react";
import { STATUS, api, fmt } from "../api";

const LEVELS = [0.9, 0.95, 0.99];

export default function WhatIfPanel({ item }) {
  const [promotion, setPromotion] = useState(false);
  const [change, setChange] = useState(0);
  const [level, setLevel] = useState(0.95);
  const [lead, setLead] = useState(3);
  const [res, setRes] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!item) return;
    let live = true;
    const t = setTimeout(() => {
      api
        .whatif({ store_nbr: item.store_nbr, family: item.family, promotion, demand_change_pct: change, service_level: level, lead_days: lead })
        .then((r) => live && (setRes(r), setError(null)))
        .catch((e) => live && setError(e));
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [item, promotion, change, level, lead]);

  if (!item) {
    return (
      <section className="card panel" id="planner">
        <div className="panel-head"><h2>Scenario Planner</h2></div>
        <p className="muted">Pick a row in the order list, an inventory alert or a demand spike to see how a promotion, a demand shift or a slower supplier changes the order.</p>
      </section>
    );
  }

  const rows = res && [
    ["Demand, planning window", res.baseline.forecast_period, res.scenario.forecast_period],
    ["Safety stock", res.baseline.safety_stock, res.scenario.safety_stock],
    ["Order quantity", res.baseline.order_qty, res.scenario.order_qty],
  ];
  const diff = res ? res.scenario.order_qty - res.baseline.order_qty : 0;

  return (
    <section className="card panel" id="planner">
      <div className="panel-head"><h2>Scenario Planner</h2></div>
      <p className="whatif-item">{fmt.title(item.family)}, store {item.store_nbr}</p>

      <div className="controls">
        <div>
          <label className="toggle">
            <input type="checkbox" checked={promotion} onChange={(e) => setPromotion(e.target.checked)} />
            Run a promotion
          </label>
          {res && <p className="muted small" style={{ margin: "4px 0 0 24px" }}>Past promotions lifted this family's sales {res.promo_lift_estimate}×.</p>}
        </div>

        <label className="control">
          <span className="control-row">Demand shift (season, event) <b>{fmt.pct(change, 0)}</b></span>
          <input type="range" min={-50} max={100} step={5} value={change} onChange={(e) => setChange(+e.target.value)} />
        </label>

        <label className="control">
          <span className="control-row">Supplier lead time <b>{lead} {lead === 1 ? "day" : "days"}</b></span>
          <input type="range" min={1} max={14} value={lead} onChange={(e) => setLead(+e.target.value)} />
        </label>

        <div className="control">
          <span className="control-row">Chance of not running out</span>
          <div className="segmented" role="group" aria-label="Service level">
            {LEVELS.map((l) => (
              <button key={l} aria-pressed={level === l} onClick={() => setLevel(l)}>{Math.round(l * 100)}%</button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="error">{error.message}</p>}
      {res && (
        <>
          <table className="tbl">
            <thead><tr><th>Units</th><th className="num">Current plan</th><th className="num">Scenario</th></tr></thead>
            <tbody>
              {rows.map(([label, a, b]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td className="num">{fmt.int(a)}</td>
                  <td className={`num ${b > a + 0.5 ? "neg" : b < a - 0.5 ? "pos" : ""}`}>{fmt.int(b)}</td>
                </tr>
              ))}
              <tr>
                <td>Status</td>
                <td className="num"><span className={`badge ${STATUS[res.baseline.status].cls}`}>{STATUS[res.baseline.status].short}</span></td>
                <td className="num"><span className={`badge ${STATUS[res.scenario.status].cls}`}>{STATUS[res.scenario.status].short}</span></td>
              </tr>
            </tbody>
          </table>
          <p className="verdict">
            {Math.abs(diff) < 1
              ? "This scenario doesn't change the order."
              : `Order ${fmt.int(Math.abs(diff))} ${diff > 0 ? "more" : "fewer"} units than the current plan (${fmt.int(res.scenario.order_qty)} in total).`}
          </p>
        </>
      )}
    </section>
  );
}
