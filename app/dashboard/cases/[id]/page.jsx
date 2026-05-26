"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest } from "../../../../lib/api";
import { getToken } from "../../../../lib/auth";

const TABS = ["timeline", "team", "documents", "tasks", "notes"];
const EVENT_TYPES = ["milestone", "hearing", "filing", "call", "meeting", "note"];
const STATUS_TYPES = ["active", "inactive", "pending"];
const PER_PAGE_OPTIONS = [5, 10, 20];

const EMPTY_EVENT = {
  title: "",
  event_type: "milestone",
  event_date: "",
  completed: false,
  status: "active",
  description: "",
};

function fmtDate(v) {
  if (!v) return "-";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("en-US");
}

function EmptyState({ text }) {
  return <div className="vilo-state-block"><p className="vilo-state">{text}</p></div>;
}

function Modal({ title, children, onClose }) {
  return (
    <div className="vilo-modal-overlay" onClick={onClose}>
      <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
        <div className="vilo-modal__header">
          <h3>{title}</h3>
          <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={onClose}>Close</button>
        </div>
        <div className="vilo-modal__body">{children}</div>
      </div>
    </div>
  );
}

export default function CaseDetailPage() {
  const { id } = useParams();
  const [activeTab, setActiveTab] = useState("timeline");
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [search, setSearch] = useState("");
  const [item, setItem] = useState(null);
  const [clients, setClients] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [notes, setNotes] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filters, setFilters] = useState({ event_type: "", status: "", completed: "", date_from: "", date_to: "" });
  const [pendingFilters, setPendingFilters] = useState({ event_type: "", status: "", completed: "", date_from: "", date_to: "" });
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);

  const [modalType, setModalType] = useState("");
  const [selectedRow, setSelectedRow] = useState(null);
  const [eventForm, setEventForm] = useState(EMPTY_EVENT);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [caseData, clientData, taskData, docData, noteData] = await Promise.all([
        apiRequest(`/api/v1/cases/${id}`),
        apiRequest(`/api/v1/clients`),
        apiRequest(`/api/v1/tasks?case_id=${id}`),
        apiRequest(`/api/v1/documents?case_id=${id}`),
        apiRequest(`/api/v1/cases/${id}/notes`),
      ]);
      setItem(caseData);
      setClients(clientData || []);
      setTasks(taskData || []);
      setDocuments(docData || []);
      setNotes(noteData || []);
      await loadTimeline(search, filters);
    } catch (err) {
      setError(err.message || "Failed to load case details");
    } finally {
      setLoading(false);
    }
  }

  async function loadTimeline(searchValue = search, activeFilters = filters) {
    const qs = new URLSearchParams();
    if (searchValue) qs.set("search", searchValue);
    if (activeFilters.event_type) qs.set("event_type", activeFilters.event_type);
    if (activeFilters.status) qs.set("status", activeFilters.status);
    if (activeFilters.completed !== "") qs.set("completed", activeFilters.completed);
    if (activeFilters.date_from) qs.set("date_from", activeFilters.date_from);
    if (activeFilters.date_to) qs.set("date_to", activeFilters.date_to);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const data = await apiRequest(`/api/v1/cases/${id}/timeline${suffix}`);
    setTimeline(data || []);
    setPage(1);
  }

  useEffect(() => { load(); }, [id]);

  function openModal(type, row = null) {
    setModalType(type);
    setSelectedRow(row);
    if (type === "add") setEventForm(EMPTY_EVENT);
    if (type === "edit" && row) {
      setEventForm({
        title: row.title || "",
        event_type: row.eventType || "milestone",
        event_date: row.eventDate ? new Date(row.eventDate).toISOString().slice(0, 10) : "",
        completed: row.completed === "Yes",
        status: row.status || "active",
        description: row.description || "",
      });
    }
  }

  async function createEvent(e) {
    e.preventDefault();
    if (!eventForm.title || !eventForm.event_type) {
      setError("Title and event type are required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${id}/timeline`, {
        method: "POST",
        body: JSON.stringify(eventForm),
      });
      setModalType("");
      await loadTimeline();
    } catch (err) {
      setError(err.message || "Failed to create timeline event");
    } finally {
      setSubmitting(false);
    }
  }

  async function updateEvent(e) {
    e.preventDefault();
    if (!selectedRow) return;
    setSubmitting(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${id}/timeline/${selectedRow.id}`, {
        method: "PATCH",
        body: JSON.stringify(eventForm),
      });
      setModalType("");
      await loadTimeline();
    } catch (err) {
      setError(err.message || "Failed to update timeline event");
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteEvent() {
    if (!selectedRow) return;
    setSubmitting(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${id}/timeline/${selectedRow.id}`, { method: "DELETE" });
      setModalType("");
      await loadTimeline();
    } catch (err) {
      setError(err.message || "Failed to delete timeline event");
    } finally {
      setSubmitting(false);
    }
  }

  async function lockEvent() {
    if (!selectedRow) return;
    setSubmitting(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${id}/timeline/${selectedRow.id}`, {
        method: "PATCH",
        body: JSON.stringify({ locked: true }),
      });
      setModalType("");
      await loadTimeline();
    } catch (err) {
      setError(err.message || "Failed to lock timeline event");
    } finally {
      setSubmitting(false);
    }
  }

  function downloadDocument(documentId) {
    const token = getToken();
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    fetch(`${base}/api/v1/documents/${documentId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Download failed");
        const blob = await r.blob();
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = "document";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(href);
      })
      .catch((err) => setError(err.message));
  }

  const timelineRows = useMemo(() => timeline.map((entry, index) => ({
    id: entry.id,
    n: index + 1,
    title: entry.title || "Timeline event",
    eventType: entry.event_type || "event",
    eventDate: entry.event_date || entry.created_at,
    completed: entry.completed ? "Yes" : "No",
    status: entry.status || "active",
    description: entry.description || "",
    locked: Boolean(entry.locked),
  })), [timeline]);

  const paginatedRows = useMemo(() => {
    const start = (page - 1) * perPage;
    return timelineRows.slice(start, start + perPage);
  }, [timelineRows, page, perPage]);

  const totalPages = Math.max(1, Math.ceil(timelineRows.length / perPage));

  const clientName = useMemo(() => clients.find((c) => c.id === item?.client_id)?.name || `#${item?.client_id || "-"}`, [clients, item]);
  const expectedCompletion = useMemo(() => {
    if (!tasks.length) return "-";
    const sorted = [...tasks].filter((t) => t.due_date).sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
    return sorted[sorted.length - 1] ? fmtDate(sorted[sorted.length - 1].due_date) : "-";
  }, [tasks]);

  return (
    <section className="dashboard-page-stack">
      <div className="case-detail-header-row">
        <h1>{item ? `${item.title} (CASE${String(item.id).padStart(6, "0")})` : "Case Detail"}</h1>
        <Link href="/dashboard/cases" className="vilo-btn vilo-btn--secondary">Back To Files</Link>
      </div>

      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading case...</p></div> : null}
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      {!loading && !error && item ? (
        <>
          <article className="dashboard-card case-summary-card">
            <div className="case-summary-grid">
              <div className="case-summary-box"><span>Client:</span><strong>{clientName}</strong></div>
              <div className="case-summary-box"><span>Case Type:</span><strong>{item.title || "-"}</strong></div>
              <div className="case-summary-box"><span>Filling Date:</span><strong>{fmtDate(item.created_at)}</strong></div>
              <div className="case-summary-box"><span>Expected Completion:</span><strong>{expectedCompletion}</strong></div>
              <div className="case-summary-box"><span>Status:</span><strong><span className={`vilo-badge vilo-badge--${item.status}`}>{item.status}</span></strong></div>
              <div className="case-summary-box"><span>Priority:</span><strong><span className={`vilo-badge vilo-badge--priority-${item.priority}`}>{item.priority}</span></strong></div>
            </div>
            <div className="case-summary-description">
              <span>Description:</span>
              <p>{item.description || "No description provided for this case yet."}</p>
            </div>
          </article>

          <article className="dashboard-card case-tabs-card">
            <div className="case-tabs-nav">
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={activeTab === t ? "case-tab-btn is-active" : "case-tab-btn"}
                  onClick={() => setActiveTab(t)}
                >
                  {t === "team" ? "Team Members" : t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {activeTab === "timeline" ? (
              <div className="case-tab-panel">
                <div className="case-tab-headline-row">
                  <h2>Timeline</h2>
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => openModal("add")}>+ Add Event</button>
                </div>
                <div className="case-toolbar-row">
                  <input
                    className="case-search-input"
                    placeholder="Search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => loadTimeline(search, filters)}>Search</button>
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => setModalType("filters")}>Filters</button>
                  <div className="case-per-page">Per Page:
                    <select value={perPage} onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}>
                      {PER_PAGE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </div>
                </div>

                <div className="vilo-table-wrap case-table-wrap">
                  <table className="team-table">
                    <thead>
                      <tr><th>#</th><th>Title</th><th>Event Type</th><th>Event Date</th><th>Completed</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                      {paginatedRows.map((row) => (
                        <tr key={row.id}>
                          <td>{row.n}</td>
                          <td>{row.title}</td>
                          <td><span className="vilo-badge vilo-badge--completed">{row.eventType}</span></td>
                          <td>{fmtDate(row.eventDate)}</td>
                          <td><span className={`vilo-badge ${row.completed === "Yes" ? "vilo-badge--active" : "vilo-badge--priority-medium"}`}>{row.completed}</span></td>
                          <td><span className={`vilo-badge ${row.status === "active" ? "vilo-badge--active" : "vilo-badge--cancelled"}`}>{row.status}</span></td>
                          <td>
                            <div className="vilo-table-actions" style={{ position: "relative" }}>
                              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setMenuOpenId(menuOpenId === row.id ? null : row.id)}>•••</button>
                              {menuOpenId === row.id ? (
                                <div className="case-actions-menu">
                                  <button type="button" onClick={() => openModal("view", row)}>View</button>
                                  <button type="button" onClick={() => openModal("edit", row)}>Edit</button>
                                  <button type="button" onClick={() => openModal("lock", row)} disabled={row.locked}>{row.locked ? "Locked" : "Lock"}</button>
                                  <button type="button" className="is-danger" onClick={() => openModal("delete", row)}>Delete</button>
                                </div>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!timelineRows.length ? <EmptyState text="No timeline events found." /> : null}
                </div>

                <div className="case-pagination-row">
                  <span>Showing {timelineRows.length ? ((page - 1) * perPage) + 1 : 0} to {Math.min(page * perPage, timelineRows.length)} of {timelineRows.length} timeline events</span>
                  <div className="vilo-table-actions">
                    <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>&lt;</button>
                    <button className="vilo-btn vilo-btn--primary vilo-btn--xs" type="button">{page}</button>
                    <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" type="button" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
                  </div>
                </div>
              </div>
            ) : null}

            {activeTab === "team" ? (
              <div className="case-tab-panel">
                <h2>Team Members</h2>
                {item.assigned_users?.length ? (
                  <div className="vilo-table-wrap case-table-wrap">
                    <table className="team-table">
                      <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead>
                      <tbody>
                        {item.assigned_users.map((u) => (
                          <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td><span className={`vilo-badge vilo-badge--${u.role}`}>{u.role}</span></td><td><span className={`vilo-badge ${u.status === "active" ? "vilo-badge--active" : "vilo-badge--cancelled"}`}>{u.status}</span></td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <EmptyState text="No team members assigned to this case." />}
              </div>
            ) : null}

            {activeTab === "documents" ? (
              <div className="case-tab-panel">
                <h2>Documents</h2>
                {documents.length ? (
                  <div className="vilo-table-wrap case-table-wrap">
                    <table className="team-table">
                      <thead><tr><th>Title</th><th>File</th><th>Category</th><th>Visibility</th><th>Action</th></tr></thead>
                      <tbody>
                        {documents.map((doc) => (
                          <tr key={doc.id}>
                            <td>{doc.title}</td><td>{doc.file_name}</td><td>{doc.category || "-"}</td>
                            <td><span className={`vilo-badge ${doc.visibility === "client_visible" ? "vilo-badge--active" : "vilo-badge--draft"}`}>{doc.visibility}</span></td>
                            <td><button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => downloadDocument(doc.id)}>Download</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <EmptyState text="No documents uploaded for this case yet." />}
              </div>
            ) : null}

            {activeTab === "tasks" ? (
              <div className="case-tab-panel">
                <h2>Tasks</h2>
                {tasks.length ? (
                  <div className="vilo-table-wrap case-table-wrap">
                    <table className="team-table">
                      <thead><tr><th>Title</th><th>Status</th><th>Priority</th><th>Due Date</th></tr></thead>
                      <tbody>
                        {tasks.map((t) => (
                          <tr key={t.id}><td>{t.title}</td><td><span className={`vilo-badge vilo-badge--${t.status}`}>{t.status}</span></td><td><span className={`vilo-badge vilo-badge--priority-${t.priority}`}>{t.priority}</span></td><td>{fmtDate(t.due_date)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <EmptyState text="No tasks linked to this case." />}
              </div>
            ) : null}

            {activeTab === "notes" ? (
              <div className="case-tab-panel">
                <h2>Notes</h2>
                {notes.length ? (
                  <div className="vilo-table-wrap case-table-wrap">
                    <table className="team-table">
                      <thead><tr><th>Note</th><th>Visibility</th><th>Created</th></tr></thead>
                      <tbody>
                        {notes.map((n) => (
                          <tr key={n.id}><td>{n.note}</td><td><span className={`vilo-badge ${n.visibility === "client_visible" ? "vilo-badge--active" : "vilo-badge--draft"}`}>{n.visibility}</span></td><td>{fmtDate(n.created_at)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <EmptyState text="No notes added for this case." />}
              </div>
            ) : null}
          </article>
        </>
      ) : null}

      {modalType === "filters" ? (
        <Modal title="Filters" onClose={() => setModalType("")}>
          <div className="vilo-form-grid">
            <select value={pendingFilters.event_type} onChange={(e) => setPendingFilters((p) => ({ ...p, event_type: e.target.value }))}>
              <option value="">All event types</option>
              {EVENT_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <select value={pendingFilters.status} onChange={(e) => setPendingFilters((p) => ({ ...p, status: e.target.value }))}>
              <option value="">All statuses</option>
              {STATUS_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <select value={pendingFilters.completed} onChange={(e) => setPendingFilters((p) => ({ ...p, completed: e.target.value }))}>
              <option value="">Any completion</option>
              <option value="true">Completed</option>
              <option value="false">Not completed</option>
            </select>
            <div className="vilo-form-row-two">
              <input type="date" value={pendingFilters.date_from} onChange={(e) => setPendingFilters((p) => ({ ...p, date_from: e.target.value }))} />
              <input type="date" value={pendingFilters.date_to} onChange={(e) => setPendingFilters((p) => ({ ...p, date_to: e.target.value }))} />
            </div>
            <div className="vilo-table-actions">
              <button className="vilo-btn vilo-btn--primary" type="button" onClick={async () => { setFilters(pendingFilters); setModalType(""); await loadTimeline(search, pendingFilters); }}>Apply</button>
              <button className="vilo-btn vilo-btn--secondary" type="button" onClick={async () => { const reset = { event_type: "", status: "", completed: "", date_from: "", date_to: "" }; setPendingFilters(reset); setFilters(reset); setModalType(""); await loadTimeline(search, reset); }}>Reset</button>
            </div>
          </div>
        </Modal>
      ) : null}

      {modalType === "add" ? (
        <Modal title="Add Timeline Event" onClose={() => setModalType("")}>
          <form className="vilo-form-grid" onSubmit={createEvent}>
            <input placeholder="Title" value={eventForm.title} onChange={(e) => setEventForm((p) => ({ ...p, title: e.target.value }))} required />
            <select value={eventForm.event_type} onChange={(e) => setEventForm((p) => ({ ...p, event_type: e.target.value }))}>
              {EVENT_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <input type="date" value={eventForm.event_date} onChange={(e) => setEventForm((p) => ({ ...p, event_date: e.target.value }))} />
            <select value={eventForm.status} onChange={(e) => setEventForm((p) => ({ ...p, status: e.target.value }))}>
              {STATUS_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <label><input type="checkbox" checked={eventForm.completed} onChange={(e) => setEventForm((p) => ({ ...p, completed: e.target.checked }))} /> Completed</label>
            <textarea placeholder="Description" value={eventForm.description} onChange={(e) => setEventForm((p) => ({ ...p, description: e.target.value }))} />
            <button className="vilo-btn vilo-btn--primary" type="submit" disabled={submitting}>{submitting ? "Saving..." : "Create Event"}</button>
          </form>
        </Modal>
      ) : null}

      {modalType === "view" && selectedRow ? (
        <Modal title="View Timeline Event" onClose={() => setModalType("")}>
          <div className="vilo-form-grid">
            <p><strong>Title:</strong> {selectedRow.title}</p>
            <p><strong>Event Type:</strong> {selectedRow.eventType}</p>
            <p><strong>Event Date:</strong> {fmtDate(selectedRow.eventDate)}</p>
            <p><strong>Completed:</strong> {selectedRow.completed}</p>
            <p><strong>Status:</strong> {selectedRow.status}</p>
            <p><strong>Description:</strong> {selectedRow.description || "-"}</p>
          </div>
        </Modal>
      ) : null}

      {modalType === "edit" && selectedRow ? (
        <Modal title="Edit Timeline Event" onClose={() => setModalType("")}>
          <form className="vilo-form-grid" onSubmit={updateEvent}>
            <input placeholder="Title" value={eventForm.title} onChange={(e) => setEventForm((p) => ({ ...p, title: e.target.value }))} required />
            <select value={eventForm.event_type} onChange={(e) => setEventForm((p) => ({ ...p, event_type: e.target.value }))}>
              {EVENT_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <input type="date" value={eventForm.event_date} onChange={(e) => setEventForm((p) => ({ ...p, event_date: e.target.value }))} />
            <select value={eventForm.status} onChange={(e) => setEventForm((p) => ({ ...p, status: e.target.value }))}>
              {STATUS_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <label><input type="checkbox" checked={eventForm.completed} onChange={(e) => setEventForm((p) => ({ ...p, completed: e.target.checked }))} /> Completed</label>
            <textarea placeholder="Description" value={eventForm.description} onChange={(e) => setEventForm((p) => ({ ...p, description: e.target.value }))} />
            <button className="vilo-btn vilo-btn--primary" type="submit" disabled={submitting}>{submitting ? "Saving..." : "Update Event"}</button>
          </form>
        </Modal>
      ) : null}

      {modalType === "delete" && selectedRow ? (
        <Modal title="Delete Timeline Event" onClose={() => setModalType("")}>
          <p>Are you sure you want to delete <strong>{selectedRow.title}</strong>?</p>
          <div className="vilo-table-actions">
            <button className="vilo-btn vilo-btn--danger" type="button" onClick={deleteEvent} disabled={submitting}>{submitting ? "Deleting..." : "Delete"}</button>
            <button className="vilo-btn vilo-btn--secondary" type="button" onClick={() => setModalType("")}>Cancel</button>
          </div>
        </Modal>
      ) : null}

      {modalType === "lock" && selectedRow ? (
        <Modal title="Lock Timeline Event" onClose={() => setModalType("")}>
          <p>Lock <strong>{selectedRow.title}</strong>? This marks it as read-only in timeline metadata.</p>
          <div className="vilo-table-actions">
            <button className="vilo-btn vilo-btn--primary" type="button" onClick={lockEvent} disabled={submitting}>{submitting ? "Locking..." : "Lock"}</button>
            <button className="vilo-btn vilo-btn--secondary" type="button" onClick={() => setModalType("")}>Cancel</button>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}
