import { Zap } from "lucide-react";
import { api, fmt } from "../api";
import { Status, useApi } from "./useApi";

export default function DemandSpikes({ onPick }) {
  const { data, error, loading } = useApi(() => api.spikes(), []);
  return (
    <section className="card panel" id="spikes">
      <div className="panel-head">
        <h2>Demand Spikes</h2>
        <a className="view-all" href="#planner">Plan</a>
      </div>
      <Status loading={loading} error={error}>
        {data && (
          <>
            <div className="spike-head">
              <span className="spike-icon"><Zap size={30} fill="#fff" strokeWidth={0} /></span>
              <div>
                <b>{data.count}</b>
                <span>store–product lines selling {data.threshold}× their normal rate this week</span>
              </div>
            </div>
            {data.items.length === 0 && <p className="muted">No unusual demand this week.</p>}
            <table className="tbl compact">
              <tbody>
                {data.items.map((r) => (
                  <tr key={`${r.store_nbr}-${r.family}`} className="clickable" onClick={() => onPick(r)}>
                    <td>Store {r.store_nbr}</td>
                    <td>{fmt.title(r.family)}</td>
                    <td className="num pos">+{fmt.int(r.change_pct)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Status>
    </section>
  );
}
