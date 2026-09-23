import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";

const API_BASE = "http://localhost:8000";
const NEEDED_COLOR = "#2a78d6";
const AVAILABLE_COLOR = "#eb6834";

interface Kpis {
  fill_rate: number;
  backup_coverage: number;
  capacity_utilization_mean: number;
  capacity_utilization_spread: number;
  total_cars: number;
  total_car_km: number;
  guardian_car_km: number;
  peer_car_km: number;
  car_km_savings: number;
  solo_transit_count: number;
  rotation_repeat_rate: number;
}

interface Exception {
  show_id: string;
  musician_count: number;
  backup_count: number;
  fully_staffed: boolean;
  backup_ready: boolean;
}

interface WeeklyCapacity {
  week: string;
  needed: number;
  available: number;
}

interface ControlTowerData {
  kpis: Kpis;
  exceptions: Exception[];
  weekly_capacity: WeeklyCapacity[];
}

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

function StatTile({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="stat-tile" title={help}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

function App() {
  const [data, setData] = useState<ControlTowerData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/control-tower`)
      .then((res) => {
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <div className="page">
        <p className="error">Couldn't load the control tower: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <p className="loading">Solving this month's schedule…</p>
      </div>
    );
  }

  const { kpis, exceptions, weekly_capacity } = data;

  return (
    <div className="page">
      <h1>Control tower</h1>
      <p className="subtitle">The state of the month at a glance.</p>

      <div className="stat-row">
        <StatTile label="Fill rate" value={pct(kpis.fill_rate)} help="Shows fully staffed as planned" />
        <StatTile
          label="Backup coverage"
          value={pct(kpis.backup_coverage)}
          help="Shows with 3 named backups, including a pianist"
        />
        <StatTile
          label="Capacity utilization"
          value={pct(kpis.capacity_utilization_mean)}
          help={`Spread ±${pct(kpis.capacity_utilization_spread)}`}
        />
        <StatTile label="Cars used" value={String(kpis.total_cars)} help={`${kpis.total_car_km.toFixed(0)} total car-km`} />
        <StatTile label="Carpool savings" value={`${kpis.car_km_savings.toFixed(0)} km`} help="Versus everyone driving solo" />
        <StatTile
          label="Rotation repeats"
          value={pct(kpis.rotation_repeat_rate)}
          help="Assignments that are repeat visits to the same facility"
        />
      </div>

      <hr />

      <h2>Needs attention</h2>
      {exceptions.length === 0 ? (
        <p className="success">Nothing needs attention this month.</p>
      ) : (
        <ul className="exceptions-list">
          {exceptions.map((row) => {
            const critical = !row.fully_staffed;
            return (
              <li key={row.show_id}>
                <span className={critical ? "status-dot critical" : "status-dot warning"} />
                <strong>{row.show_id}</strong> —{" "}
                {critical ? "not fully staffed" : "thin on backups"} ({row.musician_count} musicians,{" "}
                {row.backup_count} backups)
              </li>
            );
          })}
        </ul>
      )}

      <hr />

      <h2>Weekly capacity</h2>
      <p className="subtitle">Musician-slots needed vs. how many marked themselves available, by week.</p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={weekly_capacity}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" />
          <XAxis dataKey="week" tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="needed" name="Needed" fill={NEEDED_COLOR} radius={[4, 4, 0, 0]} />
          <Bar dataKey="available" name="Available" fill={AVAILABLE_COLOR} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default App;
