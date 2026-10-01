import { useState } from "react";
import { api } from "./api";
import CategorySales from "./components/CategorySales";
import DemandForecast from "./components/DemandForecast";
import DemandSpikes from "./components/DemandSpikes";
import Header from "./components/Header";
import InventoryAlerts from "./components/InventoryAlerts";
import KpiCards from "./components/KpiCards";
import ReorderTable from "./components/ReorderTable";
import SalesTrend from "./components/SalesTrend";
import Sidebar from "./components/Sidebar";
import StoreSegments from "./components/StoreSegments";
import TopProducts from "./components/TopProducts";
import WhatIfPanel from "./components/WhatIfPanel";
import { Status, useApi } from "./components/useApi";

const USER = { name: "Karthik", initials: "KK", role: "Admin" };

export default function App() {
  const [store, setStore] = useState(null);
  const [family, setFamily] = useState(null);
  const [status, setStatus] = useState(null);
  const [picked, setPicked] = useState(null);
  const [active, setActive] = useState("dashboard");

  const kpis = useApi(() => api.kpis(), []);
  const stores = useApi(() => api.stores(), []);
  const families = useApi(() => api.families(), []);

  const pick = (r) => {
    setPicked({ store_nbr: r.store_nbr, family: r.family });
    document.getElementById("planner")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const nav = (id) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="app">
      <Sidebar active={active} onNav={nav} updated={kpis.data?.recommendation_run} user={USER} />
      <main className="main">
        <Header user={USER} stores={stores.data} families={families.data} store={store} family={family}
                onStore={setStore} onFamily={setFamily} alerts={kpis.data?.alerts.LOW_STOCK ?? 0} asOf={kpis.data?.as_of} />

        <Status loading={kpis.loading} error={kpis.error}>
          {kpis.data && <KpiCards k={kpis.data} />}
        </Status>

        <div className="row row-trend">
          <SalesTrend store={store} family={family} />
          <CategorySales />
        </div>
        <div className="row row-half">
          <TopProducts onFamily={setFamily} />
          <InventoryAlerts onPick={pick} />
        </div>
        <div className="row row-thirds">
          <DemandForecast store={store} family={family} />
          <StoreSegments />
          <DemandSpikes onPick={pick} />
        </div>
        <div className="row row-trend">
          <ReorderTable store={store} family={family} status={status} onStatus={setStatus}
                        selected={picked} onPick={pick} counts={kpis.data?.alerts} />
          <WhatIfPanel item={picked} />
        </div>

        <p className="foot">
          Sales values in ₹ use assumed prices per product family (the source data records units only).
          Forecasts come from LightGBM models trained on Corporación Favorita sales; stock levels are simulated.
        </p>
      </main>
    </div>
  );
}
