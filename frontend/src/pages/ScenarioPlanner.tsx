import { useState } from "react";
import { API_BASE } from "../api";

interface Kpis {
  fill_rate: number;
  backup_coverage: number;
  capacity_utilization_mean: number;
  capacity_utilization_spread: number;
  total_cars: number;
  total_car_km: number;
  car_km_savings: number;
  rotation_repeat_rate: number;
}

interface ScenarioResponse {
  baseline: Kpis;
  scenario: Kpis;
}

const ROWS: { key: keyof Kpis; label: string; format: (v: number) => string }[] = [
  { key: "fill_rate", label: "Fill rate (simulated)", format: (v) => `${Math.round(v * 100)}%` },
  { key: "backup_coverage", label: "Backup coverage", format: (v) => `${Math.round(v * 100)}%` },
  { key: "capacity_utilization_mean", label: "Capacity utilization", format: (v) => `${Math.round(v * 100)}%` },
  { key: "capacity_utilization_spread", label: "Utilization spread", format: (v) => `±${Math.round(v * 100)}%` },
  { key: "total_cars", label: "Cars used", format: (v) => String(v) },
  { key: "total_car_km", label: "Total car-km", format: (v) => `${v.toFixed(0)} km` },
  { key: "car_km_savings", label: "Carpool savings", format: (v) => `${v.toFixed(0)} km` },
  { key: "rotation_repeat_rate", label: "Rotation repeats", format: (v) => `${Math.round(v * 100)}%` },
];

export default function ScenarioPlanner() {
  const [cancellationPct, setCancellationPct] = useState(12.5);
  const [removeMusicians, setRemoveMusicians] = useState(0);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScenario = () => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cancellation_p: cancellationPct / 100, remove_musicians: removeMusicians }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        return res.json();
      })
      .then(setResult)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  };

  return (
    <div>
      <h1>Scenario planner</h1>
      <p className="subtitle">What-if this month looked different — re-runs the schedule and compares it to today's plan.</p>

      <div className="scenario-controls">
        <label>
          Cancellation rate: <strong>{cancellationPct.toFixed(1)}%</strong> per musician per show
          <br />
          <span className="hint">1 cancellation per show is normal ≈ 12.5%</span>
          <input
            type="range"
            min={5}
            max={50}
            step={2.5}
            value={cancellationPct}
            onChange={(e) => setCancellationPct(Number(e.target.value))}
          />
        </label>

        <label>
          Musicians removed: <strong>{removeMusicians}</strong>
          <br />
          <span className="hint">Simulates losing volunteers — triggers a full re-solve</span>
          <input
            type="range"
            min={0}
            max={30}
            step={1}
            value={removeMusicians}
            onChange={(e) => setRemoveMusicians(Number(e.target.value))}
          />
        </label>

        <button onClick={runScenario} disabled={loading}>
          {loading ? "Running…" : "Run scenario"}
        </button>
      </div>

      {error && <p className="error">Couldn't run that scenario: {error}</p>}

      {result && (
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Today's plan</th>
              <th>This scenario</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{row.format(result.baseline[row.key])}</td>
                <td>{row.format(result.scenario[row.key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
