"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const VIEW_OPTIONS = ["month", "week", "day"];
const FILTER_OPTIONS = [
  { key: "all", label: "All" },
  { key: "court", label: "Court" },
  { key: "meeting", label: "Meeting" },
  { key: "deadline", label: "Deadline" },
  { key: "consultation", label: "Consultation" },
  { key: "reminder", label: "Task / Reminder" },
  { key: "other", label: "Other" },
];
const EVENT_TYPE_OPTIONS = [
  { value: "court", label: "Court" },
  { value: "client", label: "Meeting" },
  { value: "consultation", label: "Consultation" },
  { value: "travel", label: "Deadline" },
  { value: "staff", label: "Task / Reminder" },
  { value: "note", label: "Other" },
];
const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const CATEGORY_TO_TONE = {
  court: "is-court",
  meeting: "is-client",
  deadline: "is-travel",
  consultation: "is-consultation",
  reminder: "is-staff",
  other: "is-note",
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

function formatEventDate(date) {
  return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function formatLongDate(date) {
  return date.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function parseDateValue(value) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function normalizeValue(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ");
}

function getEventCategory(event) {
  const candidates = [
    event.event_type,
    event.type,
    event.category,
    event.eventType,
    event.status,
    event.title,
  ];

  for (const candidate of candidates) {
    const value = normalizeValue(candidate);
    if (!value) continue;

    if (value.includes("court") || value.includes("hearing") || value.includes("trial") || value.includes("appearance")) return "court";
    if (value.includes("consult")) return "consultation";
    if (value.includes("deadline") || value.includes("due") || value.includes("filing")) return "deadline";
    if (value.includes("meeting") || value.includes("client")) return "meeting";
    if (value.includes("task") || value.includes("reminder") || value.includes("todo") || value.includes("staff") || value.includes("note")) return "reminder";
  }

  return "other";
}

function getCategoryLabel(category) {
  return FILTER_OPTIONS.find((option) => option.key === category)?.label || "Other";
}

function getEventTypeLabel(type) {
  return EVENT_TYPE_OPTIONS.find((option) => option.value === type)?.label || "Other";
}

function getToneClass(category) {
  return CATEGORY_TO_TONE[category] || CATEGORY_TO_TONE.other;
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
  const [activeFilter, setActiveFilter] = useState("all");
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
    } catch {
      setError("Unable to load calendar data right now.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const queryDate = parseDateValue(searchParams.get("date"));
    if (queryDate) {
      setSelectedDate(queryDate);
      setSelectedMonth(startOfMonth(queryDate));
    }
  }, [searchParams]);

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
    const category = getEventCategory(event);
    return {
      ...event,
      start,
      dateKey: ymd(start),
      category,
      toneClass: getToneClass(category),
      displayType: getEventTypeLabel(String(event.event_type || "")),
    };
  }

  const normalizedEvents = useMemo(() => events.map(parseEvent).sort((a, b) => a.start - b.start), [events]);

  const filteredEvents = useMemo(() => {
    if (activeFilter === "all") return normalizedEvents;
    return normalizedEvents.filter((event) => event.category === activeFilter);
  }, [activeFilter, normalizedEvents]);

  const monthEvents = useMemo(
    () => normalizedEvents.filter((event) => event.start.getMonth() === selectedMonth.getMonth() && event.start.getFullYear() === selectedMonth.getFullYear()),
    [normalizedEvents, selectedMonth],
  );

  const monthCounts = useMemo(() => {
    const counts = { events: monthEvents.length, court: 0, meeting: 0, consultation: 0 };
    monthEvents.forEach((event) => {
      if (event.category === "court") counts.court += 1;
      if (event.category === "meeting") counts.meeting += 1;
      if (event.category === "consultation") counts.consultation += 1;
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

  const filteredEventsByDay = useMemo(() => {
    const map = new Map();
    filteredEvents.forEach((event) => {
      const list = map.get(event.dateKey) || [];
      list.push(event);
      map.set(event.dateKey, list);
    });
    return map;
  }, [filteredEvents]);

  const upcomingEvents = useMemo(() => {
    const now = new Date();
    return filteredEvents.filter((event) => event.start >= now).slice(0, 8);
  }, [filteredEvents]);

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

  const selectedDateKey = ymd(selectedDate);
  const selectedDateEvents = useMemo(() => eventsByDay.get(selectedDateKey) || [], [eventsByDay, selectedDateKey]);
  const selectedDateFilteredEvents = useMemo(() => filteredEventsByDay.get(selectedDateKey) || [], [filteredEventsByDay, selectedDateKey]);

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

  function focusEvent(eventId) {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("create");
    params.delete("date");
    params.set("event_id", String(eventId));
    const matched = normalizedEvents.find((event) => event.id === eventId);
    if (matched) {
      setSelectedDate(new Date(matched.start));
      setSelectedMonth(startOfMonth(matched.start));
    }
    router.push(`/dashboard/calendar?${params.toString()}`);
  }

  function selectCalendarDate(date) {
    const nextDate = new Date(date);
    setSelectedDate(nextDate);
    setSelectedMonth(startOfMonth(nextDate));
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
      setSuccess(sameMonth ? "Event created successfully." : "Event created in another month.");
      closeModal();
      await load();
    } catch {
      setError("Unable to create event. Please review the form and try again.");
    } finally {
      setSaving(false);
    }
  }

  const monthSummary = `${monthCounts.events} events scheduled in ${monthLabel(selectedMonth)}.`;
  const filterLabel = getCategoryLabel(activeFilter);
  const selectedDateHeading = formatLongDate(selectedDate);
  const selectedDateEmptyMessage = activeFilter === "all"
    ? "No events scheduled for this day."
    : `No ${filterLabel.toLowerCase()} events scheduled for this day.`;

  return (
    <section className="dashboard-page-stack calendar-page">
      <div className="calendar-page-topbar">
        <div className="calendar-page-titleblock">
          <div className="dashboard-page-heading">
            <h1>Calendar</h1>
            <p className="calendar-page-subtitle">{monthSummary}</p>
          </div>
        </div>
        <div className="calendar-page-topbar__actions">
          <div className="calendar-month-switcher">
            <button type="button" className="calendar-month-switcher__arrow" onClick={() => moveMonth(-1)} aria-label="Previous month">‹</button>
            <div className="calendar-month-switcher__label">{monthLabel(selectedMonth)}</div>
            <button type="button" className="calendar-month-switcher__arrow" onClick={() => moveMonth(1)} aria-label="Next month">›</button>
          </div>
          <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => openModalForDate(selectedDate)}>+ Add Event</button>
        </div>
      </div>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}

      <div className="calendar-layout-grid">
        <article className="dashboard-card calendar-main-card">
          <div className="calendar-main-head">
            <div className="calendar-main-head__meta">
              <p className="calendar-main-head__eyebrow">Scheduling view</p>
              <h2>{monthLabel(selectedMonth)}</h2>
            </div>
            <div className="calendar-view-toggle" role="tablist" aria-label="Calendar views">
              {VIEW_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={view === option ? "calendar-view-toggle__btn is-active" : "calendar-view-toggle__btn"}
                  onClick={() => setView(option)}
                >
                  {option[0].toUpperCase() + option.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading calendar...</p></div> : null}

          {!loading && view === "month" ? (
            <div className="calendar-month-shell">
              <div className="calendar-weekdays">
                {WEEKDAY_LABELS.map((day) => <span key={day}>{day}</span>)}
              </div>

              <div className="calendar-month-grid">
                {monthGrid.map((date) => {
                  const key = ymd(date);
                  const allDayEvents = eventsByDay.get(key) || [];
                  const filteredDayEvents = filteredEventsByDay.get(key) || [];
                  const visibleDayEvents = activeFilter === "all" ? allDayEvents : filteredDayEvents;
                  const previewEvents = visibleDayEvents.slice(0, 3);
                  const hiddenCount = Math.max(0, visibleDayEvents.length - previewEvents.length);
                  const inMonth = date.getMonth() === selectedMonth.getMonth();
                  const isToday = sameDay(date, new Date()) && inMonth;
                  const isSelectedDate = sameDay(date, selectedDate);
                  const hasFilterMatch = activeFilter !== "all" && filteredDayEvents.length > 0;
                  const isFilterMuted = activeFilter !== "all" && allDayEvents.length > 0 && filteredDayEvents.length === 0;

                  return (
                    <div
                      key={key}
                      className={`calendar-day-cell ${inMonth ? "" : "is-faded"} ${isToday ? "is-today" : ""} ${isSelectedDate ? "is-selected-date" : ""} ${hasFilterMatch ? "has-filter-match" : ""} ${isFilterMuted ? "is-filter-muted" : ""}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => selectCalendarDate(date)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          selectCalendarDate(date);
                        }
                      }}
                    >
                      <div className="calendar-day-cell__head">
                        <span className="calendar-day-number">{date.getDate()}</span>
                        {hasFilterMatch ? <span className={`calendar-day-match-dot ${getToneClass(activeFilter)}`} aria-hidden="true" /> : null}
                      </div>
                      <div className="calendar-day-events">
                        {previewEvents.map((event) => (
                          <button
                            key={event.id}
                            type="button"
                            className={`calendar-event-pill ${event.toneClass}${selectedEventId === event.id ? " is-selected" : ""}`}
                            title={`${event.title} · ${formatTime(event.start_at)}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              focusEvent(event.id);
                            }}
                          >
                            <span className="calendar-event-pill__time">{formatTime(event.start_at)}</span>
                            <span className="calendar-event-pill__title">{event.title}</span>
                          </button>
                        ))}
                        {hiddenCount ? <span className="calendar-event-more">+{hiddenCount} more</span> : null}
                        {!visibleDayEvents.length && activeFilter !== "all" && allDayEvents.length ? <span className="calendar-day-empty-hint">No {filterLabel.toLowerCase()}</span> : null}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="calendar-filters" role="toolbar" aria-label="Calendar event filters">
                {FILTER_OPTIONS.map((option) => {
                  const isActive = activeFilter === option.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      className={`calendar-filter-chip ${isActive ? "is-active" : ""}`}
                      onClick={() => setActiveFilter((current) => (current === option.key ? "all" : option.key))}
                      aria-pressed={isActive}
                    >
                      <i className={`calendar-event-dot ${getToneClass(option.key === "all" ? "other" : option.key)}`} />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {!loading && view === "week" ? (
            <div className="calendar-list-view">
              {weekDays.map((day) => {
                const key = ymd(day);
                const list = activeFilter === "all" ? (eventsByDay.get(key) || []) : (filteredEventsByDay.get(key) || []);
                return (
                  <div key={key} className="calendar-list-day">
                    <h3>{day.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</h3>
                    {list.length ? list.map((event) => (
                      <button key={event.id} type="button" className={`calendar-list-item ${event.toneClass}${selectedEventId === event.id ? " is-selected" : ""}`} onClick={() => focusEvent(event.id)}>
                        <strong>{event.title}</strong>
                        <span>{formatTime(event.start_at)}{event.case_id ? ` · Case #${event.case_id}` : ""}</span>
                      </button>
                    )) : <p className="vilo-state">{activeFilter === "all" ? "No events" : `No ${filterLabel.toLowerCase()} events`}</p>}
                  </div>
                );
              })}
            </div>
          ) : null}

          {!loading && view === "day" ? (
            <div className="calendar-list-view">
              <div className="calendar-list-day">
                <h3>{selectedDateHeading}</h3>
                {selectedDateFilteredEvents.length ? selectedDateFilteredEvents.map((event) => (
                  <button key={event.id} type="button" className={`calendar-list-item ${event.toneClass}${selectedEventId === event.id ? " is-selected" : ""}`} onClick={() => focusEvent(event.id)}>
                    <strong>{event.title}</strong>
                    <span>{formatTime(event.start_at)}{event.case_id ? ` · Case #${event.case_id}` : ""}</span>
                  </button>
                )) : <div className="vilo-state-block"><p className="vilo-state">{selectedDateEmptyMessage}</p></div>}
              </div>
            </div>
          ) : null}
        </article>

        <aside className="calendar-side-stack">
          <article className="dashboard-card calendar-side-card calendar-selected-card">
            <div className="dashboard-card__header calendar-selected-card__header">
              <div>
                <p className="calendar-main-head__eyebrow">Selected date</p>
                <h2>{selectedDateHeading}</h2>
              </div>
              <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => openModalForDate(selectedDate)}>
                Add Event
              </button>
            </div>

            {loading ? (
              <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading events...</p></div>
            ) : (
              <div className="calendar-selected-list">
                {selectedDateFilteredEvents.length ? selectedDateFilteredEvents.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    className={`calendar-upcoming-item ${event.toneClass}${selectedEventId === event.id ? " is-selected" : ""}`}
                    onClick={() => focusEvent(event.id)}
                  >
                    <div className="calendar-upcoming-item__topline">
                      <span>{getCategoryLabel(event.category)}</span>
                      <small>{formatTime(event.start_at)}</small>
                    </div>
                    <strong>{event.title}</strong>
                    <div className="calendar-upcoming-item__meta">
                      <span>{event.case_id ? `Case #${event.case_id}` : "No case linked"}</span>
                      <span>{event.location || event.displayType}</span>
                    </div>
                  </button>
                )) : (
                  <div className="calendar-selected-empty">
                    <p>{selectedDateEmptyMessage}</p>
                    {activeFilter !== "all" && selectedDateEvents.length ? <span>{selectedDateEvents.length} other event(s) exist on this date.</span> : null}
                  </div>
                )}
              </div>
            )}
          </article>

          <article className="dashboard-card calendar-side-card">
            <div className="dashboard-card__header"><h2>Upcoming</h2></div>
            {loading ? (
              <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading upcoming events...</p></div>
            ) : upcomingEvents.length ? (
              <div className="calendar-upcoming-list">
                {upcomingEvents.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    className={`calendar-upcoming-item ${event.toneClass}${selectedEventId === event.id ? " is-selected" : ""}`}
                    onClick={() => focusEvent(event.id)}
                  >
                    <div className="calendar-upcoming-item__topline">
                      <span>{formatEventDate(event.start)}</span>
                      <small>{formatTime(event.start_at)}</small>
                    </div>
                    <strong>{event.title}</strong>
                    <div className="calendar-upcoming-item__meta">
                      <span>{getCategoryLabel(event.category)}</span>
                      <span>{event.case_id ? `Case #${event.case_id}` : "No case linked"}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : <div className="vilo-state-block"><p className="vilo-state">{activeFilter === "all" ? "No upcoming events." : `No upcoming ${filterLabel.toLowerCase()} events.`}</p></div>}
          </article>

          <article className="dashboard-card calendar-side-card">
            <div className="dashboard-card__header"><h2>Monthly Overview</h2></div>
            <div className="calendar-overview-list">
              <OverviewRow label="Events" count={monthCounts.events} pct={100} tone="is-court" />
              <OverviewRow label="Court" count={monthCounts.court} pct={monthCounts.events ? Math.round((monthCounts.court / monthCounts.events) * 100) : 0} tone="is-court" />
              <OverviewRow label="Meeting" count={monthCounts.meeting} pct={monthCounts.events ? Math.round((monthCounts.meeting / monthCounts.events) * 100) : 0} tone="is-client" />
              <OverviewRow label="Consults" count={monthCounts.consultation} pct={monthCounts.events ? Math.round((monthCounts.consultation / monthCounts.events) * 100) : 0} tone="is-consultation" />
            </div>
          </article>
        </aside>
      </div>

      {modalOpen ? (
        <div className="vilo-modal-overlay" onClick={closeModal}>
          <div className="vilo-modal calendar-event-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header calendar-event-modal__header">
              <div>
                <h3>Add Event</h3>
                <p className="calendar-event-modal__copy">Create an event for {form.date || selectedDateKey}.</p>
              </div>
              <button className="calendar-event-modal__close" type="button" onClick={closeModal} aria-label="Close add event form">×</button>
            </div>

            <form onSubmit={createEvent}>
              <div className="vilo-modal__body calendar-event-modal__body">
                <div className="calendar-event-modal__section">
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-title">Event title *</label>
                    <input
                      id="calendar-event-title"
                      placeholder="Enter event title"
                      value={form.title}
                      onChange={(e) => setForm({ ...form, title: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="calendar-event-modal__grid">
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-date">Date *</label>
                    <input id="calendar-event-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
                  </div>
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-type">Type / Category *</label>
                    <select id="calendar-event-type" value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} required>
                      {EVENT_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </div>
                </div>

                <div className="calendar-event-modal__grid">
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-start">Start time *</label>
                    <input id="calendar-event-start" type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} required />
                  </div>
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-end">End time</label>
                    <input id="calendar-event-end" type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
                  </div>
                </div>

                <div className="calendar-event-modal__grid">
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-case">Related case</label>
                    <select id="calendar-event-case" value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                      <option value="">No related case</option>
                      {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                    </select>
                  </div>
                  <div className="calendar-event-modal__field">
                    <label htmlFor="calendar-event-location">Location</label>
                    <input id="calendar-event-location" placeholder="Enter location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
                  </div>
                </div>

                <div className="calendar-event-modal__field">
                  <label htmlFor="calendar-event-description">Description / Notes</label>
                  <textarea id="calendar-event-description" placeholder="Add notes or context" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                </div>
              </div>

              <div className="calendar-event-modal__footer">
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

function OverviewRow({ label, count, pct, tone }) {
  return (
    <div className="calendar-overview-row">
      <div className="calendar-overview-row__header">
        <strong>{label}</strong>
        <span>{count}</span>
      </div>
      <div className="calendar-overview-bar"><i className={tone} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
    </div>
  );
}
