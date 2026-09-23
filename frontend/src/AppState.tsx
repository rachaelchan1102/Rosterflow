import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";

export type Panel =
  | { kind: "show"; id: string }
  | { kind: "musician"; id: string }
  | { kind: "addShow"; date?: string }
  | { kind: "editShow"; id: string }
  | { kind: "musicianForm"; id?: string }
  | { kind: "availability"; id: string };

type Mode = "playground" | "coordinator";

interface AppState {
  mode: Mode;
  coordinatorAvailable: boolean;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Bumped after every change; pages refetch when it moves. */
  version: number;
  refresh: () => void;
  panels: Panel[];
  openPanel: (p: Panel) => void;
  backPanel: () => void;
  closePanels: () => void;
  toast: string | null;
  showToast: (msg: string) => void;
}

const AppContext = createContext<AppState | null>(null);

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("playground");
  const [coordinatorAvailable, setCoordinatorAvailable] = useState(false);
  const [version, setVersion] = useState(0);
  const [panels, setPanels] = useState<Panel[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const loadSession = useCallback(() => {
    api<{ mode: Mode; coordinator_available: boolean }>("/api/session").then((s) => {
      setMode(s.mode);
      setCoordinatorAvailable(s.coordinator_available);
    });
  }, []);

  useEffect(() => {
    loadSession();
    const onExpired = () => {
      setMode("playground");
      setPanels([]);
      refresh();
    };
    window.addEventListener("session-expired", onExpired);
    return () => window.removeEventListener("session-expired", onExpired);
  }, [loadSession, refresh]);

  const login = async (password: string) => {
    const { token } = await api<{ token: string }>("/api/login", { method: "POST", body: { password } });
    setToken(token);
    setMode("coordinator");
    setPanels([]);
    refresh();
  };

  const logout = async () => {
    if (getToken()) await api("/api/logout", { method: "POST" }).catch(() => undefined);
    setToken(null);
    setMode("playground");
    setPanels([]);
    refresh();
  };

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast((current) => (current === msg ? null : current)), 3500);
  }, []);

  return (
    <AppContext.Provider
      value={{
        mode, coordinatorAvailable, login, logout, version, refresh,
        panels,
        openPanel: (p) => setPanels((prev) => [...prev, p]),
        backPanel: () => setPanels((prev) => prev.slice(0, -1)),
        closePanels: () => setPanels([]),
        toast, showToast,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
