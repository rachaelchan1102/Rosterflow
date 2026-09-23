import { Fragment, useEffect, useState } from "react";
import { API_BASE } from "./api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const START_HOUR = 9;
const END_HOUR = 21;   // exclusive — last slot is 20:00-21:00
const HOURS = Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i);

interface Window {
  weekday: string;
  start_time: string;
  end_time: string;
}

function toGrid(windows: Window[]): boolean[][] {
  const grid = DAYS.map(() => HOURS.map(() => false));
  for (const w of windows) {
    const dayIdx = DAYS.indexOf(w.weekday);
    if (dayIdx === -1) continue;
    const start = Number(w.start_time.split(":")[0]);
    const end = Number(w.end_time.split(":")[0]);
    for (let h = Math.max(start, START_HOUR); h < Math.min(end, END_HOUR); h++) {
      grid[dayIdx][h - START_HOUR] = true;
    }
  }
  return grid;
}

function toWindows(grid: boolean[][]): Window[] {
  const windows: Window[] = [];
  grid.forEach((row, dayIdx) => {
    let blockStart: number | null = null;
    row.forEach((on, i) => {
      if (on && blockStart === null) blockStart = i;
      if (!on && blockStart !== null) {
        windows.push({
          weekday: DAYS[dayIdx],
          start_time: `${String(START_HOUR + blockStart).padStart(2, "0")}:00`,
          end_time: `${String(START_HOUR + i).padStart(2, "0")}:00`,
        });
        blockStart = null;
      }
    });
    if (blockStart !== null) {
      windows.push({
        weekday: DAYS[dayIdx],
        start_time: `${String(START_HOUR + blockStart).padStart(2, "0")}:00`,
        end_time: `${String(END_HOUR).padStart(2, "0")}:00`,
      });
    }
  });
  return windows;
}

export default function AvailabilityGrid({ musicianId, onClose }: { musicianId: string; onClose: () => void }) {
  const [grid, setGrid] = useState<boolean[][] | null>(null);
  const [painting, setPainting] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/musicians/${musicianId}/availability`)
      .then((res) => res.json())
      .then((windows: Window[]) => setGrid(toGrid(windows)));
  }, [musicianId]);

  if (!grid) return <p className="loading">Loading availability…</p>;

  const setCell = (day: number, hour: number, value: boolean) => {
    setGrid((prev) => {
      const next = prev!.map((row) => [...row]);
      next[day][hour] = value;
      return next;
    });
  };

  const toggleDay = (day: number) => {
    const allOn = grid[day].every(Boolean);
    setGrid((prev) => {
      const next = prev!.map((row) => [...row]);
      next[day] = next[day].map(() => !allOn);
      return next;
    });
  };

  const save = () => {
    setSaving(true);
    setError(null);
    fetch(`${API_BASE}/api/musicians/${musicianId}/availability`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toWindows(grid)),
    })
      .then((res) => {
        if (!res.ok) return res.json().then((e) => Promise.reject(new Error(e.detail)));
        onClose();
      })
      .catch((e) => setError(e.message))
      .finally(() => setSaving(false));
  };

  return (
    <div className="availability-panel" onMouseUp={() => setPainting(null)}>
      <p className="hint">Click a cell to toggle it, or click and drag to paint several at once. Click a day's name to fill/clear the whole day.</p>
      {error && <p className="error">{error}</p>}
      <div className="availability-grid" style={{ gridTemplateColumns: `60px repeat(${HOURS.length}, 1fr)` }}>
        <div />
        {HOURS.map((h) => <div key={h} className="grid-hour-label">{h}</div>)}
        {DAYS.map((day, dayIdx) => (
          <Fragment key={day}>
            <button className="grid-day-label" onClick={() => toggleDay(dayIdx)}>{day}</button>
            {HOURS.map((_, hourIdx) => {
              const on = grid[dayIdx][hourIdx];
              return (
                <div
                  key={`${day}-${hourIdx}`}
                  className={`grid-cell ${on ? "on" : ""}`}
                  onMouseDown={() => { const v = !on; setPainting(v); setCell(dayIdx, hourIdx, v); }}
                  onMouseEnter={() => { if (painting !== null) setCell(dayIdx, hourIdx, painting); }}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
      <div className="availability-actions">
        <button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save availability"}</button>
        <button className="secondary" onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
