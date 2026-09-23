import { useState, type FormEvent } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useApp } from "./AppState";
import PanelHost from "./components/PanelHost";

function LoginDialog({ onClose }: { onClose: () => void }) {
  const { login, coordinatorAvailable } = useApp();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    login(password).then(onClose).catch((err) => setError(err.message)).finally(() => setBusy(false));
  };

  return (
    <div className="modal-scrim" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Coordinator login</h2>
        <p className="muted small">
          Logging in switches to the real, saved schedule. The playground you're in now is sample data
          that resets every time you refresh.
        </p>
        {!coordinatorAvailable && (
          <p className="callout amber small">This server isn't connected to a coordinator database yet, so login will fail.</p>
        )}
        <label>Password
          <input type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="panel-footer">
          <button className="button" type="submit" disabled={busy || !password}>{busy ? "Checking…" : "Log in"}</button>
          <button className="button secondary" type="button" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </div>
  );
}

export default function Layout() {
  const { mode, logout, toast } = useApp();
  const [loginOpen, setLoginOpen] = useState(false);

  return (
    <div className="app">
      <header className="top-bar">
        <div className="brand">Music for the Golden Age · Scheduling</div>
        <nav className="top-nav">
          <NavLink to="/" end>Calendar</NavLink>
          <NavLink to="/cancel">Cancellations</NavLink>
          <NavLink to="/tools">Roster</NavLink>
          <NavLink to="/scenario">Scenario planner</NavLink>
        </nav>
        <div className="mode">
          {mode === "coordinator" ? (
            <>
              <span className="mode-badge saved">Coordinator · changes are saved</span>
              <button className="link-button" onClick={() => logout()}>Log out</button>
            </>
          ) : (
            <>
              <span className="mode-badge" title="Sample data, just for you — refreshing the page starts over">
                Playground · resets on refresh
              </span>
              <button className="link-button" onClick={() => setLoginOpen(true)}>Coordinator login</button>
            </>
          )}
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      <PanelHost />
      {loginOpen && <LoginDialog onClose={() => setLoginOpen(false)} />}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
