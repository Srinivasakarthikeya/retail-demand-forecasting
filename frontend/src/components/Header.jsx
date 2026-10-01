import { Bell, CalendarDays, Search, X } from "lucide-react";
import { useState } from "react";
import { fmt } from "../api";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
}

export default function Header({ user, stores, families, store, family, onStore, onFamily, alerts, asOf }) {
  const [q, setQ] = useState("");
  const options = [
    ...(stores || []).map((s) => ({ key: `s${s.store_nbr}`, label: `Store ${s.store_nbr} – ${s.city}`, pick: () => onStore(s.store_nbr) })),
    ...(families || []).map((f) => ({ key: `f${f}`, label: fmt.title(f), pick: () => onFamily(f) })),
  ];
  const matches = q.trim() ? options.filter((o) => o.label.toLowerCase().includes(q.toLowerCase())).slice(0, 8) : [];
  const start = asOf && new Date(new Date(asOf).getTime() - 27 * 864e5);

  return (
    <header className="header">
      <div>
        <h1>{greeting()}, {user.name} <span aria-hidden="true">👋</span></h1>
        <p>Here's what's happening with your stores today.</p>
      </div>
      <div className="header-right">
        <div className="header-tools">
          <div className="search">
            <Search size={18} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search stores or product families…" aria-label="Search stores or product families" />
            {matches.length > 0 && (
              <ul className="search-results" role="listbox">
                {matches.map((m) => (
                  <li key={m.key}><button onClick={() => { m.pick(); setQ(""); }}>{m.label}</button></li>
                ))}
              </ul>
            )}
          </div>
          <a className="bell" href="#inventory" aria-label={`${alerts} lines running out before delivery`}>
            <Bell size={20} />
            {alerts > 0 && <span>{alerts > 99 ? "99+" : alerts}</span>}
          </a>
          <span className="avatar">{user.initials}</span>
        </div>
        <div className="header-tools">
          {(store || family) && (
            <div className="active-filters">
              {store && <button onClick={() => onStore(null)}>Store {store} <X size={14} /></button>}
              {family && <button onClick={() => onFamily(null)}>{fmt.title(family)} <X size={14} /></button>}
            </div>
          )}
          {asOf && (
            <span className="date-pill">
              <CalendarDays size={16} />
              {fmt.date(start, { day: "numeric", month: "short" })} – {fmt.date(asOf)}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
