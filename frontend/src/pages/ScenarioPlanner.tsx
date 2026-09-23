import { useEffect, useState } from "react";
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

interface Facility {
  facility_id: string;
  display_name: string;
}

interface Feasibility {
  date: string;
  probability_fully_staffed: number;
  eligible_pool_size: number;
  excluded_day_conflict: number;
  excluded_over_cap: number;
  excluded_guardian_range: number;
  mean_available_count: number;
  mean_available_songs: number;
}

interface FeasibilityResponse {
  requested: Feasibility;
  alternatives: Feasibility[];
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

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

export default function ScenarioPlanner() {
  const [cancellationPct, setCancellationPct] = useState(12.5);
  const [removeMusicians, setRemoveMusicians] = useState(0);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [newShowFacility, setNewShowFacility] = useState("");
  const [newShowDate, setNewShowDate] = useState("");
  const [feasibility, setFeasibility] = useState<FeasibilityResponse | null>(null);
  const [feasibilityLoading, setFeasibilityLoading] = useState(false);
  const [feasibilityError, setFeasibilityError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/facilities`).then((res) => res.json()).then((f: Facility[]) => {
      setFacilities(f);
      if (f.length) setNewShowFacility(f[0].facility_id);
    });
  }, []);

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

  const checkFeasibility = () => {
    if (!newShowDate) {
      setFeasibilityError("Pick a date first.");
      return;
    }
    setFeasibilityLoading(true);
    setFeasibilityError(null);
    fetch(`${API_BASE}/api/feasibility`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ facility_id: newShowFacility, date: newShowDate }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        return res.json();
      })
      .then(setFeasibility)
      .catch((err) => setFeasibilityError(String(err)))
      .finally(() => setFeasibilityLoading(false));
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

      <hr />

      <h2>Will a new show fit?</h2>
      <p className="subtitle">
        Before promising a care home a date — how likely is it we could actually staff it, given what's already committed?
      </p>

      <div className="scenario-controls">
        <label>
          Facility
          <select value={newShowFacility} onChange={(e) => setNewShowFacility(e.target.value)}>
            {facilities.map((f) => <option key={f.facility_id} value={f.facility_id}>{f.facility_id}</option>)}
          </select>
        </label>
        <label>
          Requested date
          <input type="date" value={newShowDate} onChange={(e) => setNewShowDate(e.target.value)} />
        </label>
        <button onClick={checkFeasibility} disabled={feasibilityLoading}>
          {feasibilityLoading ? "Checking…" : "Check feasibility"}
        </button>
      </div>

      {feasibilityError && <p className="error">{feasibilityError}</p>}

      {feasibility && (
        <div className="feasibility-result">
          <div className="stat-tile feasibility-headline">
            <div className="stat-label">Chance {feasibility.requested.date} can be fully staffed</div>
            <div className="stat-value">{pct(feasibility.requested.probability_fully_staffed)}</div>
          </div>
          <p className="hint">
            {feasibility.requested.eligible_pool_size} musicians eligible
            ({feasibility.requested.excluded_day_conflict} already booked that day,{" "}
            {feasibility.requested.excluded_over_cap} at their monthly cap,{" "}
            {feasibility.requested.excluded_guardian_range} outside the guardian-distance limit) —
            averaging {feasibility.requested.mean_available_count.toFixed(1)} musicians and{" "}
            {feasibility.requested.mean_available_songs.toFixed(0)} songs available across simulated runs.
          </p>

          {feasibility.alternatives.length > 0 && (
            <>
              <h3>Nearby dates ranked by feasibility</h3>
              <table className="comparison-table">
                <thead>
                  <tr><th>Date</th><th>Chance fully staffed</th><th>Eligible pool</th></tr>
                </thead>
                <tbody>
                  {feasibility.alternatives.map((a) => (
                    <tr key={a.date} className={a.date === feasibility.requested.date ? "current-row" : ""}>
                      <td>{a.date}{a.date === feasibility.requested.date ? " (requested)" : ""}</td>
                      <td>{pct(a.probability_fully_staffed)}</td>
                      <td>{a.eligible_pool_size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
