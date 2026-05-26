"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  case_id: "",
  title: "",
  description: "",
  event_type: "meeting",
  start_at: "",
  end_at: "",
  location: "",
};

export default function CalendarPage() {
  const [events, setEvents] = useState([]);
  const [cases, setCases] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [eventData, caseData] = await Promise.all([
        apiRequest("/api/v1/calendar/events"),
        apiRequest("/api/v1/cases"),
      ]);
      setEvents(eventData);
      setCases(caseData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createEvent(e) {
    e.preventDefault();
    setError("");
    try {
      await apiRequest("/api/v1/calendar/events", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          case_id: form.case_id ? Number(form.case_id) : null,
          start_at: new Date(form.start_at).toISOString(),
          end_at: form.end_at ? new Date(form.end_at).toISOString() : null,
        }),
      });
      setForm(initialForm);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Calendar</h1></div>

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Create Event</h2></div>
        <form className="vilo-form-grid" onSubmit={createEvent}>
          <input placeholder="Event title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          <div className="vilo-form-row-two">
            <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
              <option value="">No linked case</option>
              {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
            <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })}>
              <option value="meeting">meeting</option>
              <option value="hearing">hearing</option>
              <option value="deadline">deadline</option>
              <option value="todo">todo</option>
              <option value="consultation">consultation</option>
            </select>
          </div>

          <div className="vilo-form-row-two">
            <input type="datetime-local" value={form.start_at} onChange={(e) => setForm({ ...form, start_at: e.target.value })} required />
            <input type="datetime-local" value={form.end_at} onChange={(e) => setForm({ ...form, end_at: e.target.value })} />
          </div>

          <input placeholder="Location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          <button type="submit">Create Event</button>
        </form>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Upcoming Events</h2></div>
        {loading ? <p className="vilo-state">Loading events...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Title</th><th>Type</th><th>Start</th><th>End</th><th>Case</th></tr></thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{event.title}</td>
                    <td><span className="vilo-badge vilo-badge--closed">{event.event_type}</span></td>
                    <td>{new Date(event.start_at).toLocaleString()}</td>
                    <td>{event.end_at ? new Date(event.end_at).toLocaleString() : "-"}</td>
                    <td>{event.case_id ? `#${event.case_id}` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
