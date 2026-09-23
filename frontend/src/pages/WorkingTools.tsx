import { useEffect, useState } from "react";
import { API_BASE } from "../api";
import AvailabilityGrid from "../AvailabilityGrid";

interface Musician {
  musician_id: string;
  display_name: string;
  age: number;
  instrument: string;
  home_region: string;
  home_lat: number;
  home_lng: number;
  transport: string;
  can_drive: boolean;
  years_with_org: number;
  max_shows_per_month: number;
  min_songs: number;
  typical_songs: number;
  max_songs: number;
}

interface Show {
  show_id: string;
  facility_id: string;
  date: string;
  start_time: string;
  duration_min: number;
  period: string;
}

interface Facility {
  facility_id: string;
  display_name: string;
}

const EMPTY_MUSICIAN: Musician = {
  musician_id: "", display_name: "", age: 18, instrument: "piano",
  home_region: "", home_lat: 43.65, home_lng: -79.38, transport: "car",
  can_drive: true, years_with_org: 0, max_shows_per_month: 2,
  min_songs: 1, typical_songs: 2, max_songs: 3,
};

const EMPTY_SHOW: Show = {
  show_id: "", facility_id: "", date: "", start_time: "14:00", duration_min: 60, period: "upcoming",
};

async function apiCall(path: string, method: string, body?: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="error working-tools-error">{message}</p>;
}

function MusiciansSection() {
  const [musicians, setMusicians] = useState<Musician[]>([]);
  const [form, setForm] = useState<Musician>(EMPTY_MUSICIAN);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [availabilityFor, setAvailabilityFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => apiCall("/api/musicians", "GET").then(setMusicians);
  useEffect(() => { refresh(); }, []);

  const startEdit = (m: Musician) => {
    setError(null);
    setEditingId(m.musician_id);
    setForm(m);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(EMPTY_MUSICIAN);
  };

  const submitMusician = () => {
    setError(null);
    const action = editingId
      ? apiCall(`/api/musicians/${editingId}`, "PUT", form)
      : apiCall("/api/musicians", "POST", form);
    action
      .then(() => { setForm(EMPTY_MUSICIAN); setEditingId(null); refresh(); })
      .catch((e) => setError(e.message));
  };

  const deleteMusician = (id: string) => {
    setError(null);
    apiCall(`/api/musicians/${id}`, "DELETE")
      .then(refresh)
      .catch((e) => setError(e.message));
  };

  return (
    <section>
      <h2>Musicians</h2>
      <ErrorBanner message={error} />
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th><th>Name</th><th>Age</th><th>Instrument</th><th>Region</th>
            <th>Monthly cap</th><th colSpan={3}></th>
          </tr>
        </thead>
        <tbody>
          {musicians.map((m) => (
            <tr key={m.musician_id}>
              <td>{m.musician_id}</td>
              <td>{m.display_name}</td>
              <td>{m.age}</td>
              <td>{m.instrument}</td>
              <td>{m.home_region}</td>
              <td>{m.max_shows_per_month}</td>
              <td><button className="link-button" onClick={() => startEdit(m)}>Edit</button></td>
              <td><button className="link-button" onClick={() => setAvailabilityFor(m.musician_id)}>Availability</button></td>
              <td><button className="link-button danger" onClick={() => deleteMusician(m.musician_id)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {availabilityFor && (
        <AvailabilityGrid musicianId={availabilityFor} onClose={() => setAvailabilityFor(null)} />
      )}

      <h3>{editingId ? `Edit ${editingId}` : "Add a musician"}</h3>
      <div className="add-form">
        <input placeholder="ID (e.g. M99)" value={form.musician_id} disabled={!!editingId}
               onChange={(e) => setForm({ ...form, musician_id: e.target.value })} />
        <input placeholder="Name" value={form.display_name}
               onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        <input type="number" placeholder="Age" value={form.age}
               onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} />
        <select value={form.instrument} onChange={(e) => setForm({ ...form, instrument: e.target.value })}>
          <option value="piano">piano</option>
          <option value="guitar">guitar</option>
          <option value="violin">violin</option>
          <option value="cello">cello</option>
        </select>
        <input placeholder="Home region" value={form.home_region}
               onChange={(e) => setForm({ ...form, home_region: e.target.value })} />
        <input type="number" step="0.0001" placeholder="Home lat" value={form.home_lat}
               onChange={(e) => setForm({ ...form, home_lat: Number(e.target.value) })} />
        <input type="number" step="0.0001" placeholder="Home lng" value={form.home_lng}
               onChange={(e) => setForm({ ...form, home_lng: Number(e.target.value) })} />
        <select value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value })}>
          <option value="car">car</option>
          <option value="transit">transit</option>
          <option value="guardian">guardian</option>
        </select>
        <label className="checkbox-label">
          <input type="checkbox" checked={form.can_drive}
                 onChange={(e) => setForm({ ...form, can_drive: e.target.checked })} />
          Can drive
        </label>
        <input type="number" placeholder="Monthly cap" value={form.max_shows_per_month}
               onChange={(e) => setForm({ ...form, max_shows_per_month: Number(e.target.value) })} />
        <input type="number" placeholder="Typical songs" value={form.typical_songs}
               onChange={(e) => setForm({ ...form, typical_songs: Number(e.target.value) })} />
        <input type="number" placeholder="Max songs" value={form.max_songs}
               onChange={(e) => setForm({ ...form, max_songs: Number(e.target.value) })} />
        <button onClick={submitMusician}>{editingId ? "Save changes" : "Add musician"}</button>
        {editingId && <button className="secondary" onClick={cancelEdit}>Cancel</button>}
      </div>
    </section>
  );
}

function ShowsSection() {
  const [shows, setShows] = useState<Show[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [form, setForm] = useState<Show>(EMPTY_SHOW);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => apiCall("/api/shows", "GET").then(setShows);
  useEffect(() => {
    refresh();
    apiCall("/api/facilities", "GET").then((f: Facility[]) => {
      setFacilities(f);
      if (f.length) setForm((prev) => ({ ...prev, facility_id: f[0].facility_id }));
    });
  }, []);

  const startEdit = (s: Show) => {
    setError(null);
    setEditingId(s.show_id);
    setForm(s);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm((prev) => ({ ...EMPTY_SHOW, facility_id: prev.facility_id }));
  };

  const submitShow = () => {
    setError(null);
    const action = editingId
      ? apiCall(`/api/shows/${editingId}`, "PUT", form)
      : apiCall("/api/shows", "POST", form);
    action
      .then(() => { setForm({ ...EMPTY_SHOW, facility_id: form.facility_id }); setEditingId(null); refresh(); })
      .catch((e) => setError(e.message));
  };

  const deleteShow = (id: string) => {
    setError(null);
    apiCall(`/api/shows/${id}`, "DELETE")
      .then(refresh)
      .catch((e) => setError(e.message));
  };

  const upcoming = shows.filter((s) => s.period === "upcoming");

  return (
    <section>
      <h2>Shows</h2>
      <p className="subtitle">Upcoming shows only ({upcoming.length} of {shows.length} total, history hidden).</p>
      <ErrorBanner message={error} />
      <table className="data-table">
        <thead>
          <tr><th>ID</th><th>Facility</th><th>Date</th><th>Time</th><th>Duration</th><th colSpan={2}></th></tr>
        </thead>
        <tbody>
          {upcoming.map((s) => (
            <tr key={s.show_id}>
              <td>{s.show_id}</td>
              <td>{s.facility_id}</td>
              <td>{s.date}</td>
              <td>{s.start_time}</td>
              <td>{s.duration_min} min</td>
              <td><button className="link-button" onClick={() => startEdit(s)}>Edit</button></td>
              <td><button className="link-button danger" onClick={() => deleteShow(s.show_id)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{editingId ? `Edit ${editingId}` : "Add a show"}</h3>
      <div className="add-form">
        <input placeholder="ID (e.g. S9999)" value={form.show_id} disabled={!!editingId}
               onChange={(e) => setForm({ ...form, show_id: e.target.value })} />
        <select value={form.facility_id} onChange={(e) => setForm({ ...form, facility_id: e.target.value })}>
          {facilities.map((f) => <option key={f.facility_id} value={f.facility_id}>{f.facility_id}</option>)}
        </select>
        <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
        <input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
        <input type="number" placeholder="Duration (min)" value={form.duration_min}
               onChange={(e) => setForm({ ...form, duration_min: Number(e.target.value) })} />
        <button onClick={submitShow}>{editingId ? "Save changes" : "Add show"}</button>
        {editingId && <button className="secondary" onClick={cancelEdit}>Cancel</button>}
      </div>
    </section>
  );
}

export default function WorkingTools() {
  return (
    <div>
      <h1>Working tools</h1>
      <p className="subtitle">Add, edit, or remove musicians and shows. Changes here affect the next solve.</p>
      <MusiciansSection />
      <hr />
      <ShowsSection />
    </div>
  );
}
