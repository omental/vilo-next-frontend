"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const DEFAULT_RATE = "250.00";

function nowLocalValue(offsetHours = 0) {
  const date = new Date();
  date.setHours(date.getHours() + offsetHours, 0, 0, 0);
  const tzOffset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - tzOffset * 60000);
  return local.toISOString().slice(0, 16);
}

function createInitialForm() {
  return {
    case_id: "",
    description: "",
    start_time: nowLocalValue(0),
    end_time: nowLocalValue(1),
    billing_mode: "billable",
    hourly_rate: DEFAULT_RATE,
  };
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function formatDuration(minutes) {
  if (!minutes || minutes < 1) return "00:00";
  const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
  const mins = String(minutes % 60).padStart(2, "0");
  return `${hours}:${mins}`;
}

function formatEntryNumber(id) {
  return `TE-${String(id).padStart(4, "0")}`;
}

function toBillingMode(type) {
  if (type === "non_billable") return "non_billable";
  if (type === "no_charge") return "no_charge";
  return "billable";
}

function toBillingType(mode) {
  if (mode === "non_billable") return "non_billable";
  if (mode === "no_charge") return "no_charge";
  return "professional_fee";
}

function getDurationMinutes(start, end) {
  if (!start || !end) return 0;
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime()) || endDate <= startDate) return 0;
  return Math.max(1, Math.round((endDate.getTime() - startDate.getTime()) / 60000));
}

function getAmountPreview(minutes, rate, mode) {
  if (mode !== "billable" || !minutes) return 0;
  const parsedRate = Number(rate || 0);
  if (!Number.isFinite(parsedRate)) return 0;
  return (minutes / 60) * parsedRate;
}

function badgeClass(type) {
  return `time-entry-badge time-entry-badge--${type}`;
}

function TimeEntriesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [entries, setEntries] = useState([]);
  const [cases, setCases] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modalError, setModalError] = useState("");
  const [modalMode, setModalMode] = useState("create");
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [search, setSearch] = useState("");
  const [dateRange, setDateRange] = useState("all");
  const [sortBy, setSortBy] = useState("newest");
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [form, setForm] = useState(createInitialForm());
  const [caseSearch, setCaseSearch] = useState("");

  async function loadEntries(nextPage = page, nextPerPage = perPage) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        per_page: String(nextPerPage),
        sort_by: sortBy,
      });
      if (search.trim()) params.set("search", search.trim());
      if (dateRange !== "all") params.set("date_range", dateRange);
      const response = await apiRequest(`/api/v1/time-entries?${params.toString()}`);
      setEntries(response.items || []);
      setTotal(response.total || 0);
      setTotalPages(response.total_pages || 1);
    } catch (err) {
      setError(err.message || "Failed to load time entries");
    } finally {
      setLoading(false);
    }
  }

  async function loadReferences() {
    try {
      const [caseRows, clientRows] = await Promise.all([
        apiRequest("/api/v1/cases").catch(() => []),
        apiRequest("/api/v1/clients").catch(() => []),
      ]);
      setCases(caseRows || []);
      setClients(clientRows || []);
    } catch {
      setCases([]);
      setClients([]);
    }
  }

  useEffect(() => {
    loadReferences();
  }, []);

  useEffect(() => {
    loadEntries(page, perPage);
  }, [page, perPage, sortBy, dateRange]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setPage(1);
      loadEntries(1, perPage);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      openCreateModal();
    }
  }, [searchParams]);

  useEffect(() => {
    const closeMenus = () => setMenuOpenId(null);
    window.addEventListener("click", closeMenus);
    return () => window.removeEventListener("click", closeMenus);
  }, []);

  const caseLookup = useMemo(() => {
    const map = new Map();
    clients.forEach((client) => map.set(client.id, client));
    return map;
  }, [clients]);

  const selectedCase = cases.find((item) => Number(item.id) === Number(form.case_id || 0));
  const selectedClient = selectedCase ? caseLookup.get(selectedCase.client_id) : null;
  const filteredCases = cases.filter((item) => {
    const clientName = caseLookup.get(item.client_id)?.name || "";
    const haystack = `${item.title} ${clientName}`.toLowerCase();
    return haystack.includes(caseSearch.trim().toLowerCase());
  });
  const durationMinutes = getDurationMinutes(form.start_time, form.end_time);
  const amountPreview = getAmountPreview(durationMinutes, form.hourly_rate, form.billing_mode);
  const startItem = total === 0 ? 0 : (page - 1) * perPage + 1;
  const endItem = total === 0 ? 0 : Math.min(total, (page - 1) * perPage + entries.length);

  function openCreateModal() {
    setSelectedEntry(null);
    setModalMode("create");
    setModalError("");
    setCaseSearch("");
    setForm(createInitialForm());
    setModalOpen(true);
  }

  function openEditModal(entry) {
    setSelectedEntry(entry);
    setModalMode("edit");
    setModalError("");
    setCaseSearch("");
    setForm({
      case_id: entry.case_id ? String(entry.case_id) : "",
      description: entry.description || "",
      start_time: entry.start_time ? new Date(new Date(entry.start_time).getTime() - new Date(entry.start_time).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : nowLocalValue(0),
      end_time: entry.end_time ? new Date(new Date(entry.end_time).getTime() - new Date(entry.end_time).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : nowLocalValue(1),
      billing_mode: toBillingMode(entry.billing_type),
      hourly_rate: entry.hourly_rate || DEFAULT_RATE,
    });
    setModalOpen(true);
  }

  function openViewModal(entry) {
    openEditModal(entry);
    setModalMode("view");
  }

  function closeModal() {
    setModalOpen(false);
    setModalError("");
    setSelectedEntry(null);
    if (searchParams.get("create") === "1") {
      router.replace("/dashboard/time-entries");
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    if (modalMode === "view") {
      closeModal();
      return;
    }
    if (!form.start_time || !form.end_time) {
      setModalError("Start time and end time are required.");
      return;
    }
    if (!durationMinutes) {
      setModalError("End time must be after start time.");
      return;
    }

    setSaving(true);
    setModalError("");
    setSuccess("");
    try {
      const payload = {
        case_id: form.case_id ? Number(form.case_id) : null,
        description: form.description.trim() || null,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        billing_type: toBillingType(form.billing_mode),
        hourly_rate: form.billing_mode === "billable" && form.hourly_rate ? String(form.hourly_rate) : null,
      };
      if (modalMode === "edit" && selectedEntry) {
        await apiRequest(`/api/v1/time-entries/${selectedEntry.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setSuccess("Time entry updated.");
      } else {
        await apiRequest("/api/v1/time-entries", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSuccess("Time entry created.");
      }
      closeModal();
      await loadEntries(page, perPage);
    } catch (err) {
      setModalError(err.message || "Failed to save time entry");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(entry) {
    if (!window.confirm("Delete this time entry?")) return;
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/api/v1/time-entries/${entry.id}`, { method: "DELETE" });
      setMenuOpenId(null);
      setSuccess("Time entry deleted.");
      await loadEntries(page, perPage);
    } catch (err) {
      setError(err.message || "Failed to delete time entry");
    }
  }

  return (
    <section className="dashboard-page-stack time-entries-page">
      <div className="time-entries-page__top">
        <div className="dashboard-page-heading">
          <h1>Time Entries</h1>
        </div>
        <button type="button" className="vilo-btn vilo-btn--primary time-entries-page__add" onClick={openCreateModal}>
          + Add Time Entry
        </button>
      </div>

      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      <article className="dashboard-card time-entries-shell">
        <div className="time-entries-toolbar">
          <label className="time-entries-search">
            <span aria-hidden="true">⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search time entries" />
          </label>

          <div className="time-entries-filters">
            <label>
              <span>Date Range:</span>
              <select value={dateRange} onChange={(event) => { setDateRange(event.target.value); setPage(1); }}>
                <option value="all">All Dates</option>
                <option value="today">Today</option>
                <option value="last_7_days">Last 7 Days</option>
                <option value="last_30_days">Last 30 Days</option>
                <option value="this_month">This Month</option>
              </select>
            </label>
            <label>
              <span>Sort By:</span>
              <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }}>
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="type">Type</option>
                <option value="amount_desc">Amount</option>
                <option value="duration_desc">Duration</option>
              </select>
            </label>
            <label>
              <span>Per Page:</span>
              <select value={perPage} onChange={(event) => { const next = Number(event.target.value); setPerPage(next); setPage(1); }}>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>
          </div>
        </div>

        <div className="time-entries-card">
          <div className="dashboard-card__header dashboard-card__header--action">
            <h2>Time Entries</h2>
          </div>

          {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading time entries...</p></div> : null}
          {!loading && !error && !entries.length ? (
            <div className="vilo-state-block">
              <p className="vilo-state">No time entries yet. Add one to start tracking billable work.</p>
            </div>
          ) : null}

          {!loading && !error && entries.length ? (
            <>
              <div className="vilo-table-wrap time-entries-table-wrap">
                <table className="team-table time-entries-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Case</th>
                      <th>Description</th>
                      <th>Start Time</th>
                      <th>End Time</th>
                      <th>Duration</th>
                      <th>Billing Type</th>
                      <th>Amount</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((entry) => (
                      <tr key={entry.id}>
                        <td>{formatEntryNumber(entry.id)}</td>
                        <td>
                          <div className="time-entry-case-cell">
                            <strong>{entry.case_title || "Unassigned"}</strong>
                            <span>{entry.client_name || entry.case_display_number || "No client"}</span>
                          </div>
                        </td>
                        <td>{entry.description || "-"}</td>
                        <td>{formatDateTime(entry.start_time)}</td>
                        <td>{formatDateTime(entry.end_time)}</td>
                        <td>{formatDuration(entry.duration_minutes)}</td>
                        <td><span className={badgeClass(entry.billing_type)}>{entry.billing_type.replaceAll("_", " ")}</span></td>
                        <td>{formatMoney(entry.amount)}</td>
                        <td>
                          <div className="vilo-table-actions time-entry-actions">
                            <button
                              type="button"
                              className="time-entry-actions__trigger"
                              aria-expanded={menuOpenId === entry.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                setMenuOpenId((openId) => (openId === entry.id ? null : entry.id));
                              }}
                            >
                              •••
                            </button>
                            {menuOpenId === entry.id ? (
                              <div className="case-actions-menu time-entry-actions__menu" onClick={(event) => event.stopPropagation()}>
                                <button type="button" onClick={() => { openViewModal(entry); setMenuOpenId(null); }}>View</button>
                                <button type="button" onClick={() => { openEditModal(entry); setMenuOpenId(null); }}>Edit</button>
                                <button type="button" className="is-danger" onClick={() => handleDelete(entry)}>Delete</button>
                              </div>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="time-entries-footer">
                <p>Showing {startItem} to {endItem} of {total} time entries</p>
                <div className="time-entries-pagination">
                  <button type="button" className="time-entries-pagination__nav" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                    ‹
                  </button>
                  {Array.from({ length: totalPages }, (_, index) => index + 1).slice(0, 5).map((value) => (
                    <button
                      key={value}
                      type="button"
                      className={value === page ? "time-entries-pagination__page is-active" : "time-entries-pagination__page"}
                      onClick={() => setPage(value)}
                    >
                      {value}
                    </button>
                  ))}
                  <button type="button" className="time-entries-pagination__next" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </article>

      {modalOpen ? (
        <div className="vilo-modal-overlay" onClick={closeModal}>
          <div className="vilo-modal time-entry-modal" onClick={(event) => event.stopPropagation()}>
            <div className="vilo-modal__header">
              <div>
                <h3>{modalMode === "edit" ? "Edit Time Entry" : modalMode === "view" ? "View Time Entry" : "Add Time Entry"}</h3>
              </div>
              <button type="button" className="time-entry-modal__close" onClick={closeModal}>×</button>
            </div>

            <form className="vilo-modal__body time-entry-modal__body" onSubmit={handleSave}>
              <div className="time-entry-modal__timer">
                <span>Timer:</span>
                <button type="button" className="vilo-btn vilo-btn--primary" disabled>Start Timer</button>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Start Time</label>
                  <input type="datetime-local" value={form.start_time} disabled={modalMode === "view"} onChange={(event) => setForm({ ...form, start_time: event.target.value })} />
                </div>
                <div>
                  <label>End Time</label>
                  <input type="datetime-local" value={form.end_time} disabled={modalMode === "view"} onChange={(event) => setForm({ ...form, end_time: event.target.value })} />
                </div>
              </div>

              <div className="time-entry-modal__summary">
                <span>Duration: {formatDuration(durationMinutes)}</span>
                <span>Amount: {formatMoney(amountPreview)}</span>
              </div>

              <div>
                <label>Case</label>
                <input
                  className="time-entry-modal__case-search"
                  value={caseSearch}
                  disabled={modalMode === "view"}
                  onChange={(event) => setCaseSearch(event.target.value)}
                  placeholder="Search case or client"
                />
                {selectedCase ? (
                  <button
                    type="button"
                    className="time-entry-case-picker is-selected"
                    disabled={modalMode === "view"}
                    onClick={() => setForm({ ...form, case_id: "" })}
                  >
                    <strong>{selectedCase.title}</strong>
                    <span>{selectedClient?.name || "Client unavailable"}</span>
                  </button>
                ) : null}
                {modalMode !== "view" ? (
                  <div className="time-entry-case-list">
                    <button type="button" className={!form.case_id ? "time-entry-case-picker is-active" : "time-entry-case-picker"} onClick={() => setForm({ ...form, case_id: "" })}>
                      <strong>No linked case</strong>
                      <span>Create an internal entry without attaching a matter.</span>
                    </button>
                    {filteredCases.slice(0, 6).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={Number(form.case_id) === Number(item.id) ? "time-entry-case-picker is-active" : "time-entry-case-picker"}
                        onClick={() => setForm({ ...form, case_id: String(item.id) })}
                      >
                        <strong>{item.title}</strong>
                        <span>{caseLookup.get(item.client_id)?.name || "Client unavailable"}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <div>
                <label>Description</label>
                <textarea value={form.description} disabled={modalMode === "view"} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Add work summary" />
              </div>

              <div>
                <label>Billing Type</label>
                <div className="time-entry-billing-options">
                  <label><input type="radio" name="billing_mode" checked={form.billing_mode === "billable"} disabled={modalMode === "view"} onChange={() => setForm({ ...form, billing_mode: "billable" })} /> Billable</label>
                  <label><input type="radio" name="billing_mode" checked={form.billing_mode === "non_billable"} disabled={modalMode === "view"} onChange={() => setForm({ ...form, billing_mode: "non_billable" })} /> Non-Billable</label>
                  <label><input type="radio" name="billing_mode" checked={form.billing_mode === "no_charge"} disabled={modalMode === "view"} onChange={() => setForm({ ...form, billing_mode: "no_charge" })} /> Mark As No Charge</label>
                </div>
              </div>

              <div>
                <label>Hourly Rate</label>
                <input type="number" min="0" step="0.01" value={form.hourly_rate} disabled={modalMode === "view" || form.billing_mode !== "billable"} onChange={(event) => setForm({ ...form, hourly_rate: event.target.value })} placeholder="250.00" />
              </div>

              {modalError ? <p className="vilo-state vilo-state--error">{modalError}</p> : null}

              <div className="time-entry-modal__actions">
                <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
                <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving || modalMode === "view"}>
                  {modalMode === "edit" ? (saving ? "Saving..." : "Save") : saving ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default function TimeEntriesPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading time entries...</p></div></section>}>
      <TimeEntriesPageContent />
    </Suspense>
  );
}
