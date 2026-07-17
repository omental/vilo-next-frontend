"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { apiRequest, apiUpload } from "../../../lib/api";
import ClientIntakeModal from "../../../components/dashboard/ClientIntakeModal";

function isArchived(client) {
  if (client?.archived_at) return true;
  return String(client?.notes || "").startsWith("[ARCHIVED]");
}

function readMetaLine(notes, label) {
  const token = `${label}:`;
  const idx = String(notes || "").indexOf(token);
  if (idx === -1) return "";
  return String(notes || "").slice(idx + token.length).split("\n")[0].trim();
}

function inferType(client) {
  if (client?.client_type) return client.client_type.toLowerCase() === "corporate" ? "Corporate" : "Individual";
  const line = readMetaLine(client?.notes, "Client Type").toLowerCase();
  if (line === "corporate") return "Corporate";
  const blob = `${client?.name || ""} ${client?.notes || ""}`.toLowerCase();
  if (blob.includes("corp") || blob.includes("company") || blob.includes("inc") || blob.includes("llc")) return "Corporate";
  return "Individual";
}

function inferPrimaryCase(client) {
  return readMetaLine(client?.notes, "Primary Case") || "-";
}

export default function ClientsPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading clients...</p></div></section>}>
      <ClientsPageContent />
    </Suspense>
  );
}

function ClientsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [tab, setTab] = useState("all");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("case");
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);

  const [actionOpenId, setActionOpenId] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editClient, setEditClient] = useState(null);
  const [deleteClient, setDeleteClient] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/api/v1/clients");
      setClients(data || []);
    } catch (err) {
      setError(err.message || "Failed to load clients");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") === "1") setCreateOpen(true);
  }, [searchParams]);

  async function uploadClientIdFile(clientId, file) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    await apiUpload(`/api/v1/clients/${clientId}/id-documents`, formData);
  }

  async function handleCreate(payload, idFile) {
    if (saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const created = await apiRequest("/api/v1/clients", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await uploadClientIdFile(created.id, idFile);
      setCreateOpen(false);
      await load();
      setSuccess("Client created successfully.");
    } catch (err) {
      setError(err.message || "Failed to create client");
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit(payload, idFile) {
    if (!editClient || saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/api/v1/clients/${editClient.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await uploadClientIdFile(editClient.id, idFile);
      setEditClient(null);
      await load();
      setSuccess("Client updated successfully.");
    } catch (err) {
      setError(err.message || "Failed to update client");
    } finally {
      setSaving(false);
    }
  }

  async function archiveClient(client) {
    if (saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/api/v1/clients/${client.id}`, {
        method: "PATCH",
        body: JSON.stringify({ archived_at: client.archived_at ? null : new Date().toISOString() }),
      });
      await load();
    } catch (err) {
      setError(err.message || "Failed to archive client");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSelectedClient() {
    if (!deleteClient || saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/api/v1/clients/${deleteClient.id}`, { method: "DELETE" });
      setDeleteClient(null);
      await load();
    } catch (err) {
      setError(err.message || "Failed to delete client");
    } finally {
      setSaving(false);
    }
  }

  const decorated = useMemo(
    () => clients.map((client) => ({
      ...client,
      archived: isArchived(client),
      clientType: inferType(client),
      primaryCase: inferPrimaryCase(client),
    })),
    [clients],
  );

  const allCount = decorated.length;
  const activeCount = decorated.filter((row) => !row.archived).length;
  const archivedCount = decorated.filter((row) => row.archived).length;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = decorated;

    if (tab === "active") rows = rows.filter((row) => !row.archived);
    if (tab === "archived") rows = rows.filter((row) => row.archived);

    if (q) {
      rows = rows.filter((row) => `${row.name || ""} ${row.email || ""} ${row.phone || ""} ${row.notes || ""} ${row.primaryCase || ""}`.toLowerCase().includes(q));
    }

    const sorters = {
      case: (a, b) => String(a.primaryCase || "").localeCompare(String(b.primaryCase || "")),
      name: (a, b) => String(a.name || "").localeCompare(String(b.name || "")),
      type: (a, b) => String(a.clientType || "").localeCompare(String(b.clientType || "")),
      date: (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0),
    };

    return [...rows].sort(sorters[sortBy] || sorters.case);
  }, [decorated, tab, search, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const pageRows = useMemo(() => {
    const start = (page - 1) * perPage;
    return filtered.slice(start, start + perPage);
  }, [filtered, page, perPage]);

  useEffect(() => {
    setPage(1);
  }, [tab, search, sortBy, perPage]);

  return (
    <section className="dashboard-page-stack">
      <div className="clients-header-row">
        <div className="dashboard-page-heading"><h1>Clients</h1></div>
        <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => setCreateOpen(true)}>+ New Client</button>
      </div>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {success ? <div className="vilo-state-block"><p className="vilo-state vilo-state--success">{success}</p></div> : null}

      <article className="dashboard-card clients-list-card">
        <div className="clients-tabs-row">
          <button type="button" className={tab === "all" ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setTab("all")}>All ({allCount})</button>
          <button type="button" className={tab === "active" ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setTab("active")}>Active ({activeCount})</button>
          <button type="button" className={tab === "archived" ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setTab("archived")}>Archived ({archivedCount})</button>
        </div>

        <div className="clients-toolbar-row">
          <input className="case-search-input" placeholder="Search" value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)} />
          <button className="vilo-btn vilo-btn--primary" type="button" onClick={() => setSearch(searchDraft)}>Search</button>
          <div className="clients-select-wrap">Sort By:
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="case">Case</option>
              <option value="name">Name</option>
              <option value="type">Client Type</option>
              <option value="date">Created Date</option>
            </select>
          </div>
          <div className="clients-select-wrap">Per Page:
            <select value={perPage} onChange={(e) => setPerPage(Number(e.target.value))}>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>

        <div className="case-tab-panel">
          <h2>Client Entries</h2>
          {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading clients...</p></div> : null}
          {!loading && !filtered.length ? <div className="vilo-state-block"><p className="vilo-state">No clients matched your current filters.</p></div> : null}

          {!loading && filtered.length ? (
            <div className="vilo-table-wrap case-table-wrap">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Client Name</th>
                    <th>Client Type</th>
                    <th>Primary Case</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((client) => (
                    <tr key={client.id} className="cases-row-link" onClick={() => router.push(`/dashboard/clients/${client.id}`)}>
                      <td><Link href={`/dashboard/clients/${client.id}`} className="cases-title-link">{client.name || "-"}</Link></td>
                      <td><span className={`vilo-badge ${client.clientType === "Corporate" ? "vilo-badge--completed" : "vilo-badge--priority-medium"}`}>{client.clientType}</span></td>
                      <td>{client.primaryCase || "-"}</td>
                      <td>{client.email || "-"}</td>
                      <td>{client.phone || "-"}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <div className="vilo-table-actions" style={{ position: "relative" }}>
                          <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => setActionOpenId((openId) => (openId === client.id ? null : client.id))}>•••</button>
                          {actionOpenId === client.id ? (
                            <div className="case-actions-menu">
                              <Link href={`/dashboard/clients/${client.id}`}>View Client</Link>
                              <button type="button" onClick={() => { setEditClient(client); setActionOpenId(null); }}>Edit</button>
                              <button type="button" onClick={() => { archiveClient(client); setActionOpenId(null); }} disabled={client.archived || saving}>{client.archived ? "Archived" : "Archive"}</button>
                              <button type="button" className="is-danger" onClick={() => { setDeleteClient(client); setActionOpenId(null); }}>Delete</button>
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

          <div className="case-pagination-row">
            <span>Showing {filtered.length ? (page - 1) * perPage + 1 : 0} to {Math.min(page * perPage, filtered.length)} of {filtered.length} client entries</span>
            <div className="vilo-table-actions">
              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>&lt;</button>
              <button className="vilo-btn vilo-btn--primary vilo-btn--xs" type="button">{page}</button>
              <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" type="button" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
            </div>
          </div>
        </div>
      </article>

      <ClientIntakeModal
        open={createOpen}
        mode="create"
        saving={saving}
        apiError={error}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
      />

      <ClientIntakeModal
        open={Boolean(editClient)}
        mode="edit"
        client={editClient}
        saving={saving}
        apiError={error}
        onClose={() => setEditClient(null)}
        onSubmit={handleEdit}
      />

      {deleteClient ? (
        <div className="vilo-modal-overlay" onClick={() => setDeleteClient(null)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Delete Client</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setDeleteClient(null)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <p>Delete <strong>{deleteClient.name || "this client"}</strong>? This cannot be undone.</p>
              <div className="vilo-table-actions">
                <button className="vilo-btn vilo-btn--danger" type="button" onClick={deleteSelectedClient} disabled={saving}>{saving ? "Deleting..." : "Delete"}</button>
                <button className="vilo-btn vilo-btn--secondary" type="button" onClick={() => setDeleteClient(null)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
