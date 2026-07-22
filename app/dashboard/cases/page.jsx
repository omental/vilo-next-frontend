"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { apiRequest } from "../../../lib/api";
import { DiscardChangesDialog, useModalCloseGuard } from "../../../components/useModalCloseGuard";

const initialForm = {
  title: "",
  description: "",
  client_id: "",
  status: "draft",
  priority: "medium",
  assigned_user_ids: [],
};

export default function CasesPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading cases...</p></div></section>}>
      <CasesPageContent />
    </Suspense>
  );
}

function CasesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const titleInputRef = useRef(null);
  const formCardRef = useRef(null);
  const [cases, setCases] = useState([]);
  const [clients, setClients] = useState([]);
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [editCase, setEditCase] = useState(null);
  const [editInitialCase, setEditInitialCase] = useState(null);
  const [archiveCase, setArchiveCase] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [createOpen, setCreateOpen] = useState(searchParams.get("create") === "1");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "active");
  const [staffFilter, setStaffFilter] = useState(searchParams.get("assigned_user_id") || "");
  const [clientFilter, setClientFilter] = useState(searchParams.get("client_id") || "");
  const [createdFrom, setCreatedFrom] = useState(searchParams.get("created_from") || "");
  const [createdTo, setCreatedTo] = useState(searchParams.get("created_to") || "");
  const [searchDraft, setSearchDraft] = useState(searchParams.get("search") || "");
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [page, setPage] = useState(Number(searchParams.get("page") || 1));
  const [perPage, setPerPage] = useState(10);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [counts, setCounts] = useState({});

  async function loadCases() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(perPage), status: statusFilter });
      if (staffFilter) params.set("assigned_user_id", staffFilter);
      if (clientFilter) params.set("client_id", clientFilter);
      if (createdFrom) params.set("created_from", createdFrom);
      if (createdTo) params.set("created_to", createdTo);
      if (search.trim()) params.set("search", search.trim());
      const caseData = await apiRequest(`/api/v1/cases/query?${params.toString()}`);
      setCases(caseData.items || []);
      setTotal(caseData.total || 0);
      setTotalPages(caseData.total_pages || 1);
      setCounts(Object.fromEntries((caseData.counts || []).map((item) => [item.status, item.count])));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    Promise.all([apiRequest("/api/v1/clients"), apiRequest("/api/v1/team")])
      .then(([clientData, teamData]) => {
        setClients(clientData || []);
        setTeam((teamData || []).filter((u) => u.role !== "client"));
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchDraft), 300);
    return () => window.clearTimeout(timer);
  }, [searchDraft]);

  useEffect(() => {
    loadCases();
    const params = new URLSearchParams(searchParams.toString());
    [["status", statusFilter], ["assigned_user_id", staffFilter], ["client_id", clientFilter], ["created_from", createdFrom], ["created_to", createdTo], ["search", search]].forEach(([key, value]) => value ? params.set(key, value) : params.delete(key));
    page > 1 ? params.set("page", String(page)) : params.delete("page");
    router.replace(`/dashboard/cases${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
  }, [clientFilter, createdFrom, createdTo, page, perPage, search, staffFilter, statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  function changeFilter(setter, value) {
    setPage(1);
    setter(value);
  }

  function clearFilters() {
    setStatusFilter("all");
    setStaffFilter("");
    setClientFilter("");
    setCreatedFrom("");
    setCreatedTo("");
    setSearchDraft("");
    setSearch("");
    setPage(1);
  }

  useEffect(() => {
    const shouldOpen = searchParams.get("create") === "1";
    setCreateOpen(shouldOpen);
  }, [searchParams]);

  useEffect(() => {
    if (!createOpen) return;
    formCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    titleInputRef.current?.focus();
  }, [createOpen]);

  async function createCase(e) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          client_id: Number(form.client_id),
        }),
      });
      setForm(initialForm);
      setCreateOpen(false);
      setSuccess("Case created successfully.");
      await loadCases();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function toggleUser(userId) {
    const has = form.assigned_user_ids.includes(userId);
    setForm({
      ...form,
      assigned_user_ids: has
        ? form.assigned_user_ids.filter((id) => id !== userId)
        : [...form.assigned_user_ids, userId],
    });
  }

  async function updateCase(e) {
    e.preventDefault();
    if (!editCase || saving) return;
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${editCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editCase.title,
          description: editCase.description || "",
          status: editCase.status,
          priority: editCase.priority,
        }),
      });
      setEditCase(null);
      setEditInitialCase(null);
      await loadCases();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function doArchiveCase() {
    if (!archiveCase) return;
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${archiveCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "archived" }),
      });
      setArchiveCase(null);
      setMenuOpenId(null);
      await loadCases();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function restoreCase(caseRow) {
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/cases/${caseRow.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "active" }),
      });
      setMenuOpenId(null);
      setSuccess("Case restored to Active.");
      await loadCases();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function openEditCase(caseRow) {
    setEditCase(caseRow);
    setEditInitialCase(caseRow);
    setMenuOpenId(null);
  }

  function closeEditCase() {
    setEditCase(null);
    setEditInitialCase(null);
  }

  const editCaseDirty = Boolean(editCase) && JSON.stringify(editCase) !== JSON.stringify(editInitialCase);
  const editCloseGuard = useModalCloseGuard({ open: Boolean(editCase), isDirty: editCaseDirty, isSubmitting: saving, onClose: closeEditCase });

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading dashboard-page-heading--split">
        <h1>Cases</h1>
        <button
          type="button"
          className={createOpen ? "vilo-btn vilo-btn--secondary" : "vilo-btn vilo-btn--primary"}
          aria-expanded={createOpen}
          onClick={() => {
            setCreateOpen((open) => !open);
            setSuccess("");
          }}
        >
          {createOpen ? "Hide Form" : "Create Case"}
        </button>
      </div>

      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}

      {createOpen ? (
        <article ref={formCardRef} className="dashboard-card vilo-form-card vilo-collapsible-card">
          <form className="vilo-form-grid vilo-collapsible-card__body" onSubmit={createCase}>
            <input ref={titleInputRef} placeholder="Case title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

            <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} required>
              <option value="">Select client</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>

            <div className="vilo-form-row-two">
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="closed">closed</option>
                <option value="archived">archived</option>
              </select>

              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>

            <div className="vilo-checkbox-grid">
              <div className="case-assign-heading"><p>Assign Users</p></div>
              <select value="" onChange={(e) => { if (!e.target.value) return; toggleUser(Number(e.target.value)); }}>
                <option value="">Select team member</option>
                {team.filter((user) => !form.assigned_user_ids.includes(user.id)).map((user) => (
                  <option key={user.id} value={user.id}>{user.name} ({user.role})</option>
                ))}
              </select>
              <div className="case-assigned-list">
                {form.assigned_user_ids.length ? form.assigned_user_ids.map((userId) => {
                  const member = team.find((u) => u.id === userId);
                  if (!member) return null;
                  return (
                    <span key={userId} className="case-assigned-pill">
                      {member.name} ({member.role})
                      <button type="button" onClick={() => toggleUser(userId)} aria-label={`Remove ${member.name}`}>×</button>
                    </span>
                  );
                }) : <span className="case-assigned-empty">No team members selected.</span>}
              </div>
            </div>

            <button type="submit" disabled={saving}>{saving ? "Creating..." : "Create Case"}</button>
          </form>
        </article>
      ) : null}

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Case List</h2></div>
        <div className="cases-status-tabs" role="tablist" aria-label="Case status">
          {[
            ["active", "Active"], ["draft", "Draft"], ["closed", "Closed"], ["archived", "Archived"], ["all", "All"],
          ].map(([value, label]) => (
            <button key={value} type="button" role="tab" aria-selected={statusFilter === value} className={`case-tab-btn${statusFilter === value ? " is-active" : ""}`} onClick={() => changeFilter(setStatusFilter, value)}>
              {label} <span>{value === "all" ? Object.values(counts).reduce((sum, count) => sum + count, 0) : counts[value] || 0}</span>
            </button>
          ))}
        </div>
        <div className="cases-filter-grid">
          <label><span>Search</span><input type="search" value={searchDraft} onChange={(event) => changeFilter(setSearchDraft, event.target.value)} placeholder="Name, number, or client" /></label>
          <label><span>Assigned staff</span><select value={staffFilter} onChange={(event) => changeFilter(setStaffFilter, event.target.value)}><option value="">All staff</option>{team.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}</select></label>
          <label><span>Client</span><select value={clientFilter} onChange={(event) => changeFilter(setClientFilter, event.target.value)}><option value="">All clients</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
          <label><span>Created from</span><input type="date" value={createdFrom} onChange={(event) => changeFilter(setCreatedFrom, event.target.value)} /></label>
          <label><span>Created to</span><input type="date" value={createdTo} onChange={(event) => changeFilter(setCreatedTo, event.target.value)} /></label>
          <button type="button" className="vilo-btn vilo-btn--secondary" onClick={clearFilters}>Clear filters</button>
        </div>
        {loading ? <p className="vilo-state">Loading cases...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error && cases.length === 0 ? <p className="vilo-state">No cases match the current filters.</p> : null}

        {!loading && !error && cases.length > 0 ? (
          <div className={`vilo-table-wrap case-table-wrap${menuOpenId ? " case-table-wrap--menu-visible" : ""}`}>
            <table className="team-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Client</th>
                  <th className="w-24 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="cases-row-link" onClick={() => { if (menuOpenId !== c.id) router.push(`/dashboard/cases/${c.id}`); }}>
                    <td><Link href={`/dashboard/cases/${c.id}`} className="cases-title-link">{c.title}</Link></td>
                    <td><span className={`vilo-badge vilo-badge--${c.status}`}>{c.status}</span></td>
                    <td><span className={`vilo-badge vilo-badge--priority-${c.priority}`}>{c.priority}</span></td>
                    <td>{c.client_name || `#${c.client_id}`}</td>
                    <td className="w-24 align-middle" onClick={(e) => e.stopPropagation()}>
                      <div className="vilo-table-actions case-row-actions">
                        <button
                          type="button"
                          className="vilo-btn vilo-btn--ghost vilo-btn--xs inline-flex h-8 w-8 items-center justify-center p-0 text-base leading-none"
                          onClick={() => setMenuOpenId(menuOpenId === c.id ? null : c.id)}
                        >
                          •••
                        </button>
                        {menuOpenId === c.id ? (
                          <div className="case-actions-menu">
                            <Link href={`/dashboard/cases/${c.id}`}>View</Link>
                            <button type="button" onClick={() => openEditCase(c)}>Edit</button>
                            {c.status === "archived" ? <button type="button" onClick={() => restoreCase(c)}>Restore</button> : <button type="button" className="is-danger" onClick={() => setArchiveCase(c)}>Archive</button>}
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {!loading && !error && total > 0 ? (
          <div className="case-pagination-row cases-list-pagination">
            <span>Showing {(page - 1) * perPage + 1}-{Math.min(page * perPage, total)} of {total}</span>
            <div className="vilo-table-actions">
              <select aria-label="Cases per page" value={perPage} onChange={(event) => { setPage(1); setPerPage(Number(event.target.value)); }}><option value="10">10</option><option value="25">25</option><option value="50">50</option></select>
              <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
              <span>Page {page} of {totalPages}</span>
              <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</button>
            </div>
          </div>
        ) : null}
      </article>

      {editCase ? (
        <div className="vilo-modal-overlay" onClick={editCloseGuard.requestClose}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Edit Case</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={editCloseGuard.requestClose} disabled={saving}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <form className="vilo-form-grid" onSubmit={updateCase}>
                <input value={editCase.title || ""} onChange={(e) => setEditCase((p) => ({ ...p, title: e.target.value }))} required />
                <textarea value={editCase.description || ""} onChange={(e) => setEditCase((p) => ({ ...p, description: e.target.value }))} />
                <div className="vilo-form-row-two">
                  <select value={editCase.status} onChange={(e) => setEditCase((p) => ({ ...p, status: e.target.value }))}>
                    <option value="draft">draft</option>
                    <option value="active">active</option>
                    <option value="closed">closed</option>
                    <option value="archived">archived</option>
                  </select>
                  <select value={editCase.priority} onChange={(e) => setEditCase((p) => ({ ...p, priority: e.target.value }))}>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </div>
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={editCloseGuard.requestClose} disabled={saving}>Cancel</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Save Changes"}</button>
                </div>
              </form>
            </div>
          </div>
          <DiscardChangesDialog open={editCloseGuard.confirmDiscard} onKeepEditing={editCloseGuard.keepEditing} onDiscard={editCloseGuard.discard} />
        </div>
      ) : null}

      {archiveCase ? (
        <div className="vilo-modal-overlay" onClick={() => setArchiveCase(null)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Archive Case</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setArchiveCase(null)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <p>Archive <strong>{archiveCase.title}</strong>? You can still view it in archived status.</p>
              <div className="vilo-table-actions">
                <button type="button" className="vilo-btn vilo-btn--danger" onClick={doArchiveCase} disabled={saving}>{saving ? "Archiving..." : "Archive"}</button>
                <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => setArchiveCase(null)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
