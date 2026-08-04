import { useQuery } from "@tanstack/react-query";
import { Link, Outlet } from "react-router-dom";
import { getCurrentHousehold } from "../../api/households";
import { useAuthStore } from "../../auth/authStore";

export function Layout() {
  const clear = useAuthStore((s) => s.clear);
  const { data: household } = useQuery({ queryKey: ["household"], queryFn: getCurrentHousehold });

  return (
    <div className="app-shell">
      <header className="app-nav">
        <Link to="/" className="brand">
          MaintainIt
        </Link>
        {household && <span className="household-name">{household.name}</span>}
        <nav>
          <Link to="/">Assets</Link>
          <Link to="/settings">Settings</Link>
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
