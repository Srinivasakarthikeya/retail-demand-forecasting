import { PALETTE, api, fmt } from "../api";
import Donut from "./Donut";
import { Status, useApi } from "./useApi";

export default function StoreSegments() {
  const { data, error, loading } = useApi(() => api.storeTypes(), []);
  const rows = data?.map((r) => ({ ...r, legend: `Type ${r.type} (${r.stores} ${r.stores === 1 ? "store" : "stores"})` }));
  const stores = data?.reduce((s, r) => s + r.stores, 0);
  return (
    <section className="card panel" id="stores">
      <div className="panel-head"><h2>Store Segmentation</h2></div>
      <Status loading={loading} error={error}>
        {rows && (
          <Donut rows={rows} valueKey="sales_inr" labelKey="type" colors={PALETTE}
                 center={fmt.int(stores)} sub="Stores" formatValue={(v) => fmt.inr(v)} />
        )}
      </Status>
    </section>
  );
}
