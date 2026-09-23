import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../AppState";
import { formatDate } from "../format";
import type { ShowDetail } from "../types";
import { CoverageBar, StatusBadge } from "./Status";

export default function ShowPanel({ showId }: { showId: string }) {
  const { version, refresh, openPanel, closePanels, showToast } = useApp();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ShowDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [banMenuFor, setBanMenuFor] = useState<string | null>(null);

  useEffect(() => {
    api<ShowDetail>(`/api/shows/${showId}/detail`).then(setDetail).catch((e) => setError(e.message));
  }, [showId, version]);

  if (error) return <p className="error">{error}</p>;
  if (!detail) return <p className="muted">Loading…</p>;

  const act = (fn: () => Promise<unknown>, msg: string) => {
    setError(null);
    fn().then(() => { showToast(msg); refresh(); }).catch((e) => setError(e.message));
  };

  const toggleLock = (musicianId: string, locked: boolean) =>
    act(() => locked
        ? api(`/api/locks?musician_id=${musicianId}&show_id=${showId}`, { method: "DELETE" })
        : api("/api/locks", { method: "POST", body: { musician_id: musicianId, show_id: showId } }),
      locked ? "Unlocked" : "Locked — the next re-solve will keep them here");

  const ban = (musicianId: string, scope: "show" | "facility") => {
    setBanMenuFor(null);
    act(() => api("/api/bans", { method: "POST", body: { musician_id: musicianId, scope,
                                                          target_id: scope === "show" ? showId : detail.facility_id } }),
        "Ban added — re-solve the draft to apply it");
  };

  const removeBan = (b: ShowDetail["bans"][number]) =>
    act(() => api(`/api/bans?musician_id=${b.musician_id}&scope=${b.scope}&target_id=${b.target_id}`, { method: "DELETE" }),
        "Ban removed");

  const startCancellation = (musicianId: string) => {
    closePanels();
    navigate(`/cancel?show=${showId}&musician=${musicianId}`);
  };

  const c = detail.coverage;
  return (
    <div className="panel-body">
      <div className="panel-title">
        <h2>{detail.facility_name}</h2>
        <p className="muted">
          {formatDate(detail.date)} · {detail.start_time} · {detail.duration_min} min
        </p>
        <div className="panel-tags">
          <StatusBadge status={detail.status} />
          {detail.changed_since_publish && <span className="tag">Changed since publish</span>}
          {!detail.has_piano_onsite && <span className="tag">Bring a keyboard</span>}
        </div>
      </div>

      {detail.reasons.length > 0 && (
        <div className={`callout ${detail.status}`}>
          <strong>Why it's flagged</strong>
          <ul>{detail.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}

      <section className="panel-section">
        <CoverageBar label="Songs covered" value={c.songs_total} target={c.songs_target}
                     status={c.songs_total >= c.songs_target ? "green" : "red"} />
        <CoverageBar label="Musicians (target)" value={c.musician_count} target={c.target_musicians}
                     status={c.musician_count < c.min_musicians ? "red" : c.musician_count < c.target_musicians ? "amber" : "green"} />
        <p className="small muted">
          Minimum {c.min_musicians} musicians · {c.has_pianist ? "✓ pianist on the show" : "✕ no pianist"}
        </p>
      </section>

      <section className="panel-section">
        <h3>Playing ({detail.roster.length})</h3>
        <ul className="person-list">
          {detail.roster.map((m) => (
            <li key={m.musician_id}>
              <button className="person-name" onClick={() => openPanel({ kind: "musician", id: m.musician_id })}>
                {m.name}
              </button>
              <span className="muted small">{m.instrument} · {m.songs} song{m.songs !== 1 ? "s" : ""}</span>
              <span className="row-actions">
                <button className={`chip-button ${m.locked ? "active" : ""}`} onClick={() => toggleLock(m.musician_id, m.locked)}
                        title={m.locked ? "Locked on this show — click to unlock" : "Keep them on this show no matter what"}>
                  {m.locked ? "🔒 Locked" : "Lock"}
                </button>
                <span className="menu-wrap">
                  <button className="chip-button" onClick={() => setBanMenuFor(banMenuFor === m.musician_id ? null : m.musician_id)}>
                    Ban…
                  </button>
                  {banMenuFor === m.musician_id && (
                    <span className="menu">
                      <button onClick={() => ban(m.musician_id, "show")}>From this show</button>
                      <button onClick={() => ban(m.musician_id, "facility")}>From {detail.facility_name} entirely</button>
                    </span>
                  )}
                </span>
                <button className="chip-button danger" onClick={() => startCancellation(m.musician_id)}>Cancelled</button>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel-section">
        <h3>Backups, in call order</h3>
        {detail.backups.length === 0 ? (
          <p className="muted small">No backups right now — see "Why it's flagged" above.</p>
        ) : (
          <ol className="backup-list">
            {detail.backups.map((b) => (
              <li key={b.musician_id}>
                <button className="person-name" onClick={() => openPanel({ kind: "musician", id: b.musician_id })}>
                  {b.name}
                </button>
                {b.is_pianist && <span className="tag">pianist</span>}
                <div className="small muted">{b.reason}</div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="panel-section">
        <h3>Getting there</h3>
        <ul className="car-list">
          {detail.cars.map((car, i) => (
            <li key={i}>
              <strong>{car.driver === "a guardian" ? "Guardian drives" : `${car.driver} drives`}</strong>
              <span className="muted small"> · {car.distance_km.toFixed(0)} km</span>
              <div className="small">{car.riders.join(", ")}</div>
            </li>
          ))}
        </ul>
        {detail.solo_transit.length > 0 && (
          <p className="small muted">On their own (transit): {detail.solo_transit.join(", ")}</p>
        )}
      </section>

      {detail.bans.length > 0 && (
        <section className="panel-section">
          <h3>Bans affecting this show</h3>
          <ul className="person-list">
            {detail.bans.map((b) => (
              <li key={`${b.musician_id}-${b.scope}`}>
                <span>{b.name}</span>
                <span className="muted small">{b.scope === "show" ? "this show" : "whole location"}</span>
                <span className="row-actions"><button className="chip-button" onClick={() => removeBan(b)}>Remove</button></span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="panel-footer">
        <button className="button secondary" onClick={() => openPanel({ kind: "editShow", id: showId })}>Edit show details</button>
      </div>
    </div>
  );
}
