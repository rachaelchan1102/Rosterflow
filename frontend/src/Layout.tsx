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
        <NavLink to="/tools" className={({ isActive }) => (isActive ? "active" : "")}>
          Working tools
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
