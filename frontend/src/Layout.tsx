import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="page">
      <nav className="top-nav">
        <NavLink to="/" className={({ isActive }) => (isActive ? "active" : "")}>
          Control tower
        </NavLink>
        <NavLink to="/scenario" className={({ isActive }) => (isActive ? "active" : "")}>
          Scenario planner
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
