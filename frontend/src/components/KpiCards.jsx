import { ArrowDown, ArrowUp, Package, PackageCheck, ShoppingCart, Truck } from "lucide-react";
import { fmt } from "../api";

function Change({ value, good = "up", label }) {
  if (value == null) return <small>{label}</small>;
  const up = value >= 0;
  const ok = (up && good === "up") || (!up && good === "down");
  const Icon = up ? ArrowUp : ArrowDown;
  return (
    <>
      <em className={ok ? "pos" : "neg"}><Icon size={16} strokeWidth={2.5} />{fmt.pct(value)}</em>
      <small>{label}</small>
    </>
  );
}

export default function KpiCards({ k }) {
  const atRisk = k.alerts.LOW_STOCK;
  const cards = [
    { title: "Total Sales", value: fmt.inr(k.sales_inr_28d), icon: ShoppingCart, tone: "red",
      foot: <Change value={k.sales_inr_change_pct} label="vs previous 28 days" /> },
    { title: "Units Sold", value: fmt.short(k.sales_last_28d), icon: Package, tone: "blue",
      foot: <Change value={k.sales_change_pct} label="vs previous 28 days" /> },
    { title: "Units to Order", value: fmt.short(k.units_to_order), icon: Truck, tone: "green",
      foot: <small>across {fmt.int(k.alerts.REORDER + k.alerts.LOW_STOCK)} store–product lines</small> },
    { title: "Lines in Stock", value: fmt.int(k.lines_in_stock), icon: PackageCheck, tone: "purple",
      foot: (
        <>
          <em className="neg"><ArrowDown size={16} strokeWidth={2.5} />{fmt.int(atRisk)} at risk</em>
          <small>of {fmt.int(k.lines_total)} lines</small>
        </>
      ) },
  ];
  return (
    <section className="kpis" id="dashboard">
      {cards.map(({ title, value, icon: Icon, tone, foot }) => (
        <div key={title} className="card kpi">
          <span className={`kpi-icon tone-${tone}`}><Icon size={26} strokeWidth={1.8} /></span>
          <div>
            <span className="kpi-title">{title}</span>
            <b className="kpi-value">{value}</b>
            <div className="kpi-foot">{foot}</div>
          </div>
        </div>
      ))}
    </section>
  );
}
