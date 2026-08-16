import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";
import { getCurrentHousehold } from "../../api/households";
import { useAuthStore } from "../../auth/authStore";

function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive ? "active" : undefined;
}

export function Layout() {
  const clear = useAuthStore((s) => s.clear);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });

  return (
    <div className="app-shell">
      <header className="app-nav">
        <Link to="/" className="brand">
          <img src="/icon-192.png" alt="" />
          Trend & Tend
        </Link>
        {household && <span className="household-name">{household.name}</span>}
        <nav>
          <NavLink to="/" end className={navLinkClass}>
            Assets
          </NavLink>
          <NavLink to="/household" className={navLinkClass}>
            Household
          </NavLink>
          <NavLink to="/import" className={navLinkClass}>
            Import
          </NavLink>
          <NavLink to="/export" className={navLinkClass}>
            Export
          </NavLink>
          <NavLink to="/settings" className={navLinkClass}>
            Settings
          </NavLink>
          <button type="button" onClick={() => clear()}>
            Log out
          </button>
        </nav>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
