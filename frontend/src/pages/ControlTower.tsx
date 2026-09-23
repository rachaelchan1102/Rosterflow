import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useApp } from "../AppState";
import { StatusBadge } from "../components/Status";
import { formatDate, formatMonth, isoDate, parseDate, pct } from "../format";
import type { Change, Kpis, ScheduleView, ShowSummary, Status } from "../types";

type Filter = "all" | "attention" | "red";
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function matches(show: ShowSummary, filter: Filter): boolean {
  if (filter === "red") return show.status === "red";
  if (filter === "attention") return show.status !== "green";
  return true;
}

function Delta({ now, then }: { now: number; then?: number }) {
  if (then === undefined) return null;
  const diff = Math.round((now - then) * 100);
  const text = diff === 0 ? "no change since publish"
    : `${diff > 0 ? "▲ up" : "▼ down"} ${Math.abs(diff)} pts since publish`;
  return <span className="delta"> · {text}</span>;
}

function ChangeList({ changes }: { changes: Change[] }) {
  return (
    <ul className="change-list">
      {changes.map((c, i) => (
        <li key={i} className={c.change}>
          <strong>{c.change === "added" ? "+" : "−"} {c.musician_name}</strong>{" "}
          {c.change === "added" ? "added to" : "taken off"} {c.facility_name} {c.date ? `(${formatDate(c.date)})` : "(a removed show)"}
          {c.reason && <span className="muted"> — {c.reason}</span>}
        </li>
      ))}
    </ul>
  );
}

function DraftBar({ view, onResolved }: { view: ScheduleView; onResolved: (changes: Change[]) => void }) {
  const { refresh, showToast } = useApp();
  const [busy, setBusy] = useState<"resolve" | "publish" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showChanges, setShowChanges] = useState(false);
  const s = view.state;

  const resolve = () => {
    setBusy("resolve");
    setError(null);
    api<{ changes: Change[] }>("/api/schedule/resolve", { method: "POST" })
      .then((r) => { onResolved(r.changes); refresh(); showToast(r.changes.length ? `Re-solved — ${r.changes.length} changes` : "Re-solved — nothing needed to move"); })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  };

  const publish = () => {
    setBusy("publish");
    setError(null);
    api("/api/schedule/publish", { method: "POST" })
      .then(() => { refresh(); showToast("Published — this is now the schedule of record"); })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(null));
  };

  const changeCount = s.unpublished_roster_changes.length;
  return (
    <div className="draft-bar-wrap">
      {s.needs_resolve && (
        <div className="callout amber draft-stale">
          <span><strong>The draft is out of date.</strong> {s.needs_resolve}</span>
          <button className="button" onClick={resolve} disabled={busy !== null}>
            {busy === "resolve" ? "Re-solving…" : "Re-solve draft"}
          </button>
        </div>
      )}
      <div className={`draft-bar ${s.has_unpublished_changes ? "dirty" : "clean"}`}>
        <div>
          {!s.published && <><strong>Draft</strong> · never published — nothing is final until you publish.</>}
          {s.published && s.has_unpublished_changes && (
            <>
              <strong>Draft</strong> · differs from the published schedule
              {changeCount > 0 && (
                <> — <button className="link-button" onClick={() => setShowChanges(!showChanges)}>
                  {changeCount} roster change{changeCount !== 1 ? "s" : ""} {showChanges ? "▾" : "▸"}
                </button></>
              )}
            </>
          )}
          {s.published && !s.has_unpublished_changes && <><strong>Published</strong> · the draft matches the schedule of record.</>}
        </div>
        <div className="draft-actions">
          {!s.needs_resolve && (
            <button className="button secondary" onClick={resolve} disabled={busy !== null}>
              {busy === "resolve" ? "Re-solving…" : "Re-solve"}
            </button>
          )}
          <button className="button" onClick={publish} disabled={busy !== null || !s.has_unpublished_changes}>
            {busy === "publish" ? "Publishing…" : "Publish"}
          </button>
        </div>
      </div>
      {showChanges && <ChangeList changes={s.unpublished_roster_changes} />}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

function KpiTile({ label, value, status, sub, active, onClick }: {
  label: string; value: string; status: Status; sub?: ReactNode; active: boolean; onClick: () => void;
}) {
  return (
    <button className={`kpi-tile ${status} ${active ? "active" : ""}`} onClick={onClick}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <StatusBadge status={status} compact />
      {sub && <span className="kpi-sub">{sub}</span>}
    </button>
  );
}

function KpiStrip({ kpis, published, attention, filter, setFilter }: {
  kpis: Kpis; published: Kpis | null; attention: { red: number; amber: number }; filter: Filter; setFilter: (f: Filter) => void;
}) {
  const fillStatus: Status = kpis.fill_rate >= 1 ? "green" : "red";
  const backupStatus: Status = kpis.backup_coverage >= 0.9 ? "green" : kpis.backup_coverage >= 0.7 ? "amber" : "red";
  const attentionStatus: Status = attention.red > 0 ? "red" : attention.amber > 0 ? "amber" : "green";
  const toggle = (f: Filter) => setFilter(filter === f ? "all" : f);
  return (
    <div className="kpi-strip">
      <KpiTile label="Backup coverage" value={pct(kpis.backup_coverage)} status={backupStatus} active={filter === "attention"}
               onClick={() => toggle("attention")}
               sub={<>shows with 3 backups incl. a pianist<Delta now={kpis.backup_coverage} then={published?.backup_coverage} /></>} />
      <KpiTile label="Needs attention" value={String(attention.red + attention.amber)} status={attentionStatus}
               active={filter === "attention"} onClick={() => toggle("attention")}
               sub={`${attention.red} not fully staffed · ${attention.amber} thin on backups`} />
      <KpiTile label="Fully staffed" value={pct(kpis.fill_rate)} status={fillStatus} active={filter === "red"}
               onClick={() => toggle("red")}
               sub={<>as planned, before any cancellations<Delta now={kpis.fill_rate} then={published?.fill_rate} /></>} />
    </div>
  );
}

function Roadmap({ shows, onOpen }: { shows: ShowSummary[]; onOpen: (s: ShowSummary) => void }) {
  const today = isoDate(new Date());
  const next = shows.filter((s) => s.date >= today).slice(0, 8);
  if (next.length === 0) return null;
  return (
    <div className="roadmap">
      <h3>Next up</h3>
      <div className="roadmap-strip">
        {next.map((s) => (
          <button key={s.show_id} className={`roadmap-card ${s.status}`} onClick={() => onOpen(s)}>
            <span className="roadmap-date">{formatDate(s.date)} · {s.start_time}</span>
            <span className="roadmap-facility">{s.facility_name}</span>
            <span className="roadmap-meta">
              <StatusBadge status={s.status} compact /> {s.musician_count}/{s.target_musicians} musicians · {s.backup_count} backups
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Calendar({ month, shows, filter, onOpen, onAdd }: {
  month: string; shows: ShowSummary[]; filter: Filter; onOpen: (s: ShowSummary) => void; onAdd: (date: string) => void;
}) {
  const first = parseDate(`${month}-01`);
  const lead = (first.getDay() + 6) % 7;   // Monday-first
  const daysInMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const byDate = new Map<string, ShowSummary[]>();
  shows.forEach((s) => byDate.set(s.date, [...(byDate.get(s.date) ?? []), s]));
  const today = isoDate(new Date());

  const cells: (string | null)[] = [...Array(lead).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  while (cells.length % 7) cells.push(null);

  return (
    <div className="calendar">
      {WEEKDAYS.map((d) => <div key={d} className="calendar-weekday">{d}</div>)}
      {cells.map((date, i) => {
        if (!date) return <div key={`blank-${i}`} className="calendar-cell blank" />;
        const dayShows = byDate.get(date) ?? [];
        return (
          <div key={date} className={`calendar-cell ${date === today ? "today" : ""}`}>
            <div className="calendar-day">
              <span>{Number(date.slice(8))}</span>
              {date >= today && (
                <button className="add-show-button" title="Add a show on this day" onClick={() => onAdd(date)}>+</button>
              )}
            </div>
            {dayShows.map((s) => (
              <button key={s.show_id} className={`show-chip ${s.status} ${matches(s, filter) ? "" : "dimmed"}`}
                      onClick={() => onOpen(s)} title={s.reasons.join("; ") || "On track"}>
                <StatusBadge status={s.status} compact />
                <span className="chip-text">{s.start_time} {s.facility_name}</span>
                {s.locked_count > 0 && <span aria-label="has locks">🔒</span>}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function AtAGlance({ view }: { view: ScheduleView }) {
  const k = view.kpis;
  return (
    <details className="at-a-glance">
      <summary>This month at a glance — travel, fairness, rotation</summary>
      <div className="glance-grid">
        <div><span className="kpi-label">Capacity used</span><strong>{pct(k.capacity_utilization_mean)}</strong>
          <span className="small muted">of everyone's monthly caps · spread ±{pct(k.capacity_utilization_spread)}</span></div>
        <div><span className="kpi-label">Cars</span><strong>{k.total_cars}</strong>
          <span className="small muted">{k.total_car_km.toFixed(0)} car-km ({k.guardian_car_km.toFixed(0)} by guardians)</span></div>
        <div><span className="kpi-label">Carpool savings</span><strong>{k.car_km_savings.toFixed(0)} km</strong>
          <span className="small muted">vs. everyone driving alone · {k.solo_transit_count} trips by transit</span></div>
        <div><span className="kpi-label">Repeat visits</span><strong>{pct(k.rotation_repeat_rate)}</strong>
          <span className="small muted">of assignments go back to a location they've played recently</span></div>
      </div>
      <h3>Musician-slots needed vs. marked available, by week</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={view.weekly_capacity}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="week" tick={{ fontSize: 11 }} tickFormatter={(w: string) => formatDate(w.slice(0, 10))} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="needed" name="Needed" fill="#2a78d6" radius={[4, 4, 0, 0]} />
          <Bar dataKey="available" name="Marked available" fill="#eb6834" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </details>
  );
}

export default function ControlTower() {
  const { version, openPanel } = useApp();
  const [view, setView] = useState<ScheduleView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [pickedMonth, setMonth] = useState<string | null>(null);
  const [justResolved, setJustResolved] = useState<Change[] | null>(null);

  useEffect(() => {
    api<ScheduleView>("/api/schedule").then(setView).catch((e) => setError(e.message));
  }, [version]);

  const months = useMemo(() => [...new Set((view?.shows ?? []).map((s) => s.date.slice(0, 7)))].sort(), [view]);
  const thisMonth = isoDate(new Date()).slice(0, 7);
  const month = pickedMonth ?? months.find((m) => m >= thisMonth) ?? months[0];

  if (error) return <p className="error">Couldn't load the schedule: {error}</p>;
  if (!view || !month) return <p className="muted loading">Loading this month's schedule…</p>;

  const attention = {
    red: view.shows.filter((s) => s.status === "red").length,
    amber: view.shows.filter((s) => s.status === "amber").length,
  };
  const monthIdx = months.indexOf(month);
  const open = (s: ShowSummary) => { setMonth(s.date.slice(0, 7)); openPanel({ kind: "show", id: s.show_id }); };

  return (
    <div>
      <DraftBar view={view} onResolved={setJustResolved} />
      {justResolved && justResolved.length > 0 && (
        <div className="callout neutral">
          <div className="callout-head">
            <strong>What the last re-solve changed</strong>
            <button className="link-button" onClick={() => setJustResolved(null)}>Dismiss</button>
          </div>
          <ChangeList changes={justResolved} />
        </div>
      )}

      <KpiStrip kpis={view.kpis} published={view.published_kpis} attention={attention} filter={filter} setFilter={setFilter} />
      <Roadmap shows={view.shows} onOpen={open} />

      <div className="calendar-head">
        <div className="month-nav">
          <button className="button secondary" disabled={monthIdx <= 0} onClick={() => setMonth(months[monthIdx - 1])}>‹</button>
          <h2>{formatMonth(month)}</h2>
          <button className="button secondary" disabled={monthIdx >= months.length - 1} onClick={() => setMonth(months[monthIdx + 1])}>›</button>
        </div>
        <div className="legend">
          <StatusBadge status="green" /> <StatusBadge status="amber" /> <StatusBadge status="red" />
          {filter !== "all" && <button className="link-button" onClick={() => setFilter("all")}>Show all shows</button>}
        </div>
      </div>
      <Calendar month={month} shows={view.shows} filter={filter} onOpen={open}
                onAdd={(date) => openPanel({ kind: "addShow", date })} />

      <AtAGlance view={view} />
    </div>
  );
}
