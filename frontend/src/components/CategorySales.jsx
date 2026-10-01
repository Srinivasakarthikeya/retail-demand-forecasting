import { PALETTE, api, fmt } from "../api";
import Donut from "./Donut";
import { Status, useApi } from "./useApi";

export default function CategorySales() {
  const { data, error, loading } = useApi(() => api.departments(), []);
  const total = data?.reduce((s, r) => s + r.sales_inr, 0);
  return (
    <section className="card panel">
      <div className="panel-head"><h2>Department Sales</h2></div>
      <Status loading={loading} error={error}>
        {data && (
          <Donut rows={data} valueKey="sales_inr" labelKey="department" colors={PALETTE}
                 center={fmt.inr(total)} sub="Total Sales" formatValue={(v) => fmt.inr(v)} />
        )}
      </Status>
    </section>
  );
}
