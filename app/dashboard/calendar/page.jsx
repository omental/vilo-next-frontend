"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const VIEW_OPTIONS = ["month", "week", "day"];
const EVENT_TYPES = ["court", "client", "consultation", "travel", "staff", "note"];

const TYPE_CLASS = {
  court: "is-court",
  client: "is-client",
  consultation: "is-consultation",
  travel: "is-travel",
  staff: "is-staff",
  note: "is-note",
  hearing: "is-court",
  meeting: "is-client",
  deadline: "is-travel",
  todo: "is-note",
};

const initialForm = {
  title: "",
  event_type: "court",
  date: "",
  start_time: "",
  end_time: "",
  case_id: "",
  location: "",
  description: "",
};

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function startOfWeek(date) {
  const copy = new Date(date);
  const day = copy.getDay();
  copy.setDate(copy.getDate() - day);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function ymd(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatTime(dateStr) {
  return new Date(dateStr).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export default function CalendarPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading calendar...</p></div></section>}>
      <CalendarPageContent />
    </Suspense>
  );
}

function CalendarPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [events, setEvents] = useState([]);
  const [cases, setCases] = useState([]);
  const [view, setView] = useState("month");
  const [selectedMonth, setSelectedMonth] = useState(startOfMonth(new Date()));
  const [selectedDate, setSelectedDate] = useState(new Date());

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(initialForm);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [eventData, caseData] = await Promise.all([
        apiRequest("/api/v1/calendar/events"),
        apiRequest("/api/v1/cases"),
      ]);
      setEvents(eventData || []);
      setCases(caseData || []);
    } catch (err) {
      setError(err.message || "Failed to load calendar data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    const queryDate = parseDateValue(searchParams.get("date"));
    openModalForDate(queryDate || selectedDate, false);
  }, [searchParams]);

  function monthLabel(date) {
    return date.toLocaleDateString([], { month: "long", year: "numeric" });
  }

  function parseEvent(event) {
    const start = new Date(event.start_at);
    return {
      ...event,
      start,
      dateKey: ymd(start),
      eventType: String(event.event_type || "note").toLowerCase(),
    };
  }

  const normalizedEvents = useMemo(() => events.map(parseEvent).sort((a, b) => a.start - b.start), [events]);

  const monthEvents = useMemo(
    () => normalizedEvents.filter((event) => event.start.getMonth() === selectedMonth.getMonth() && event.start.getFullYear() === selectedMonth.getFullYear()),
    [normalizedEvents, selectedMonth],
  );

  const monthCounts = useMemo(() => {
    const counts = { events: monthEvents.length, court: 0, client: 0, consultation: 0 };
    monthEvents.forEach((event) => {
      const t = TYPE_CLASS[event.eventType] || "is-note";
      if (t === "is-court") counts.court += 1;
      if (t === "is-client") counts.client += 1;
      if (t === "is-consultation") counts.consultation += 1;
    });
    return counts;
  }, [monthEvents]);

  const eventsByDay = useMemo(() => {
    const map = new Map();
    normalizedEvents.forEach((event) => {
      const list = map.get(event.dateKey) || [];
      list.push(event);
      map.set(event.dateKey, list);
    });
    return map;
  }, [normalizedEvents]);

  const upcomingEvents = useMemo(() => {
    const now = new Date();
    return normalizedEvents.filter((event) => event.start >= now).slice(0, 8);
  }, [normalizedEvents]);

  const monthGrid = useMemo(() => {
    const start = startOfMonth(selectedMonth);
    const end = endOfMonth(selectedMonth);
    const gridStart = new Date(start);
    gridStart.setDate(start.getDate() - start.getDay());
    const gridEnd = new Date(end);
    gridEnd.setDate(end.getDate() + (6 - end.getDay()));

    const days = [];
    for (const date = new Date(gridStart); date <= gridEnd; date.setDate(date.getDate() + 1)) {
      days.push(new Date(date));
    }
    return days;
  }, [selectedMonth]);

  const weekDays = useMemo(() => {
    const weekStart = startOfWeek(selectedDate);
    return Array.from({ length: 7 }, (_, idx) => {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + idx);
      return date;
    });
  }, [selectedDate]);

  const dayEvents = useMemo(() => {
    const key = ymd(selectedDate);
    return eventsByDay.get(key) || [];
  }, [eventsByDay, selectedDate]);

  const selectedEventId = Number(searchParams.get("event_id") || 0);

  useEffect(() => {
    if (!selectedEventId) return;
    const matched = normalizedEvents.find((event) => event.id === selectedEventId);
    if (!matched) return;
    setSelectedDate(new Date(matched.start));
    setSelectedMonth(startOfMonth(matched.start));
  }, [normalizedEvents, selectedEventId]);

  function moveMonth(delta) {
    setSelectedMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  }

  function openModalForDate(date, syncQuery = true) {
    const d = new Date(date);
    setSelectedDate(d);
    setSelectedMonth(startOfMonth(d));
    setForm({
      ...initialForm,
      date: ymd(d),
      start_time: "09:00",
      end_time: "10:00",
    });
    setModalOpen(true);
    if (syncQuery) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("create", "1");
      params.set("date", ymd(d));
      router.replace(`/dashboard/calendar?${params.toString()}`);
    }
  }

  function closeModal() {
    setModalOpen(false);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("create");
    params.delete("date");
    const next = params.toString();
    router.replace(next ? `/dashboard/calendar?${next}` : "/dashboard/calendar");
  }

  async function createEvent(e) {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!form.title.trim() || !form.event_type || !form.date || !form.start_time) {
      setError("Title, Event Type, Date and Start Time are required.");
      return;
    }

    setSaving(true);
    try {
      const startAt = new Date(`${form.date}T${form.start_time}`);
      const endAt = form.end_time ? new Date(`${form.date}T${form.end_time}`) : null;
      await apiRequest("/api/v1/calendar/events", {
        method: "POST",
        body: JSON.stringify({
          case_id: form.case_id ? Number(form.case_id) : null,
          title: form.title,
          description: form.description || null,
          event_type: form.event_type,
          start_at: startAt.toISOString(),
          end_at: endAt ? endAt.toISOString() : null,
          location: form.location || null,
        }),
      });

      const createdMonth = new Date(`${form.date}T00:00:00`);
      const sameMonth = createdMonth.getMonth() === selectedMonth.getMonth() && createdMonth.getFullYear() === selectedMonth.getFullYear();
      if (!sameMonth) {
        setSuccess("Event created in another month.");
      } else {
        setSuccess("Event created successfully.");
      }
      closeModal();
      await load();
    } catch (err) {
      setError(err.message || "Failed to create event");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="dashboard-page-stack calendar-page">
      <div className="clients-header-row">
        <div className="dashboard-page-heading"><h1>Calendar</h1></div>
        <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => openModalForDate(selectedDate)}>+ Add Event</button>
      </div>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}

      <div className="calendar-layout-grid">
        <article className="dashboard-card calendar-main-card">
          <div className="calendar-main-head">
            <div className="calendar-month-controls">
              <h2>{monthLabel(selectedMonth)}</h2>
              <div className="vilo-table-actions">
                <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => moveMonth(-1)}>‹</button>
                <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => moveMonth(1)}>›</button>
              </div>
            </div>
            <div className="calendar-view-toggle">
              {VIEW_OPTIONS.map((option) => (
                <button key={option} type="button" className={view === option ? "vilo-btn vilo-btn--primary vilo-btn--xs" : "vilo-btn vilo-btn--ghost vilo-btn--xs"} onClick={() => setView(option)}>
                  {option[0].toUpperCase() + option.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading calendar...</p></div> : null}

          {!loading && view === "month" ? (
            <div>
              <div className="calendar-weekdays">
                {[
                  "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                ].map((day) => <span key={day}>{day}</span>)}
              </div>
              <div className="calendar-month-grid">
                {monthGrid.map((date) => {
                  const key = ymd(date);
                  const dayEventsList = (eventsByDay.get(key) || []).slice(0, 3);
                  const inMonth = date.getMonth() === selectedMonth.getMonth();
                  const isToday = sameDay(date, new Date()) && inMonth;
                  return (
                    <button
                      type="button"
                      key={key}
                      className={`calendar-day-cell ${inMonth ? "" : "is-faded"} ${isToday ? "is-today" : ""}`}
                      onClick={() => openModalForDate(date)}
                    >
                      <span className="calendar-day-number">{date.getDate()}</span>
                      <div className="calendar-day-events">
                        {dayEventsList.map((event) => (
                          <span
                            key={event.id}
                            className={`calendar-event-pill ${TYPE_CLASS[event.eventType] || "is-note"}${selectedEventId === event.id ? " is-selected" : ""}`}
                            title={event.title}
                          >
                            {formatTime(event.start_at)} {event.title}
                          </span>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="calendar-legend">
                {EVENT_TYPES.map((type) => (
                  <span key={type}><i className={`calendar-event-dot ${TYPE_CLASS[type] || "is-note"}`} />{type[0].toUpperCase() + type.slice(1)}</span>
                ))}
              </div>
            </div>
          ) : null}

          {!loading && view === "week" ? (
            <div className="calendar-list-view">
              {weekDays.map((day) => {
                const key = ymd(day);
                const list = eventsByDay.get(key) || [];
                return (
                  <div key={key} className="calendar-list-day">
                    <h3>{day.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</h3>
                    {list.length ? list.map((event) => (
                      <div key={event.id} className={`calendar-list-item ${TYPE_CLASS[event.eventType] || "is-note"}${selectedEventId === event.id ? " is-selected" : ""}`}>
                        <strong>{event.title}</strong>
                        <span>{formatTime(event.start_at)}{event.case_id ? ` · Case #${event.case_id}` : ""}</span>
                      </div>
                    )) : <p className="vilo-state">No events</p>}
                  </div>
                );
              })}
            </div>
          ) : null}

          {!loading && view === "day" ? (
            <div className="calendar-list-view">
              <div className="calendar-list-day">
                <h3>{selectedDate.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</h3>
                {dayEvents.length ? dayEvents.map((event) => (
                  <div key={event.id} className={`calendar-list-item ${TYPE_CLASS[event.eventType] || "is-note"}${selectedEventId === event.id ? " is-selected" : ""}`}>
                    <strong>{event.title}</strong>
                    <span>{formatTime(event.start_at)}{event.case_id ? ` · Case #${event.case_id}` : ""}</span>
                  </div>
                )) : <div className="vilo-state-block"><p className="vilo-state">No events for this day.</p></div>}
              </div>
            </div>
          ) : null}
        </article>

        <aside className="calendar-side-stack">
          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Upcoming</h2></div>
            {upcomingEvents.length ? (
              <div className="calendar-upcoming-list">
                {upcomingEvents.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    className={`calendar-upcoming-item ${TYPE_CLASS[event.eventType] || "is-note"}${selectedEventId === event.id ? " is-selected" : ""}`}
                    onClick={() => router.push(`/dashboard/calendar?event_id=${event.id}`)}
                  >
                    <span>{event.start.toLocaleDateString([], { month: "short", day: "numeric" })} · {formatTime(event.start_at)}</span>
                    <strong>{event.title}</strong>
                    <small>{event.case_id ? `Case #${event.case_id}` : "No case linked"}</small>
                  </button>
                ))}
              </div>
            ) : <div className="vilo-state-block"><p className="vilo-state">No upcoming events.</p></div>}
          </article>

          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Monthly Overview</h2></div>
            <div className="calendar-overview-list">
              <OverviewRow label="Events" count={monthCounts.events} pct={100} />
              <OverviewRow label="Court" count={monthCounts.court} pct={monthCounts.events ? Math.round((monthCounts.court / monthCounts.events) * 100) : 0} />
              <OverviewRow label="Client" count={monthCounts.client} pct={monthCounts.events ? Math.round((monthCounts.client / monthCounts.events) * 100) : 0} />
              <OverviewRow label="Consults" count={monthCounts.consultation} pct={monthCounts.events ? Math.round((monthCounts.consultation / monthCounts.events) * 100) : 0} />
            </div>
          </article>
        </aside>
      </div>

      {modalOpen ? (
        <div className="vilo-modal-overlay" onClick={closeModal}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Add Event</h3>
              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={closeModal}>Close</button>
            </div>
            <form className="vilo-modal__body vilo-form-grid" onSubmit={createEvent}>
              <input placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
              <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} required>
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{t[0].toUpperCase() + t.slice(1)}</option>)}
              </select>
              <div className="vilo-form-row-two">
                <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
                <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                  <option value="">Related Case (Optional)</option>
                  {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </div>
              <div className="vilo-form-row-two">
                <input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} required />
                <input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
              </div>
              <input placeholder="Location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
              <textarea placeholder="Description / Notes" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <div className="vilo-table-actions">
                <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Create Event"}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function OverviewRow({ label, count, pct }) {
  return (
    <div className="calendar-overview-row">
      <div><strong>{label}</strong><span>{count}</span></div>
      <div className="calendar-overview-bar"><i style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
    </div>
  );
}

function parseDateValue(value) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
