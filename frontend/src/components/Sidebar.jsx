import { BarChart3, Boxes, ExternalLink, LayoutDashboard, ShoppingBasket, SlidersHorizontal, Store, TrendingUp, Zap } from "lucide-react";
import { API_BASE, fmt } from "../api";

export const NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "sales", label: "Sales Analytics", icon: BarChart3 },
  { id: "forecasting", label: "Demand Forecasting", icon: TrendingUp },
  { id: "inventory", label: "Inventory Management", icon: Boxes },
  { id: "stores", label: "Store Analytics", icon: Store },
  { id: "spikes", label: "Demand Spikes", icon: Zap },
  { id: "planner", label: "Scenario Planner", icon: SlidersHorizontal },
];

export function Logo() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
      <rect width="44" height="44" rx="12" fill="#e3141f" />
      <rect x="10" y="24" width="6" height="10" rx="1.5" fill="#fff" />
      <rect x="19" y="17" width="6" height="17" rx="1.5" fill="#fff" />
      <rect x="28" y="10" width="6" height="24" rx="1.5" fill="#fff" opacity="0.85" />
    </svg>
  );
}

export default function Sidebar({ active, onNav, updated, user }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo />
        <div>
          <b>ShelfIQ</b>
          <span>Retail Intelligence</span>
        </div>
      </div>
      <nav>
        {NAV.map(({ id, label, icon: Icon }) => (
          <button key={id} className={`nav-item${active === id ? " active" : ""}`} onClick={() => onNav(id)}>
            <Icon size={20} strokeWidth={1.8} />
            {label}
          </button>
        ))}
        <a className="nav-item" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
          <ShoppingBasket size={20} strokeWidth={1.8} />
          API Reference
          <ExternalLink size={14} style={{ marginLeft: "auto", opacity: 0.6 }} />
        </a>
      </nav>
      <div className="updated">
        <span>Data last updated</span>
        <b><i className="live" />{updated ? fmt.date(updated, { day: "numeric", month: "short", year: "numeric" }) : "–"}</b>
      </div>
      <div className="user">
        <span className="avatar">{user.initials}</span>
        <div><b>{user.name}</b><span>{user.role}</span></div>
      </div>
    </aside>
  );
}
