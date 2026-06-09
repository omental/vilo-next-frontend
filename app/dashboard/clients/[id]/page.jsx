"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiDownload, apiRequest, apiUpload } from "../../../../lib/api";
import { getToken } from "../../../../lib/auth";
import ClientIntakeModal from "../../../../components/dashboard/ClientIntakeModal";

function readMetaLine(notes, label) {
  const token = `${label}:`;
  const idx = String(notes || "").indexOf(token);
  if (idx === -1) return "";
  return String(notes || "").slice(idx + token.length).split("\n")[0].trim();
}

function clientType(client) {
  if (client?.client_type) return client.client_type.toLowerCase() === "corporate" ? "Corporate" : "Individual";
  const type = readMetaLine(client?.notes, "Client Type").toLowerCase();
  if (type === "corporate") return "Corporate";
  return "Individual";
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function ClientDetailPage() {
  const { id } = useParams();
  const router = useRouter();

  const [client, setClient] = useState(null);
  const [cases, setCases] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [idDocuments, setIdDocuments] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [team, setTeam] = useState([]);
  const [invoices, setInvoices] = useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [timelineTab, setTimelineTab] = useState("all");
  const [timelineDraft, setTimelineDraft] = useState("");
  const [timelineSearch, setTimelineSearch] = useState("");
  const [timelineType, setTimelineType] = useState("all");
  const [timelineOrder, setTimelineOrder] = useState("newest");

  const [documentDraft, setDocumentDraft] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [documentOrder, setDocumentOrder] = useState("newest");
  const [deleteDocumentId, setDeleteDocumentId] = useState(null);
  const [replaceTarget, setReplaceTarget] = useState(null);
  const [replaceFile, setReplaceFile] = useState(null);
  const [replaceNotes, setReplaceNotes] = useState("");
  const [versionTarget, setVersionTarget] = useState(null);
  const [versionRows, setVersionRows] = useState([]);
  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const clientData = await apiRequest(`/api/v1/clients/${id}`);
      setClient(clientData);

      const results = await Promise.allSettled([
        apiRequest("/api/v1/cases"),
        apiRequest(`/api/v1/clients/${id}/id-documents`),
        apiRequest("/api/v1/tasks"),
        apiRequest("/api/v1/team"),
        apiRequest("/api/v1/invoices"),
        apiRequest("/api/v1/documents"),
      ]);

      setCases(results[0].status === "fulfilled" ? (results[0].value || []) : []);
      setIdDocuments(results[1].status === "fulfilled" ? (results[1].value || []) : []);
      setTasks(results[2].status === "fulfilled" ? (results[2].value || []) : []);
      setTeam(results[3].status === "fulfilled" ? (results[3].value || []) : []);
      setInvoices(results[4].status === "fulfilled" ? (results[4].value || []) : []);
      setDocuments(results[5].status === "fulfilled" ? (results[5].value || []) : []);
    } catch (err) {
      setError(err.message || "Failed to load client details");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (id) load();
  }, [id]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function handleEdit(payload, idFile) {
    if (!client) return;
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/clients/${client.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      if (idFile) {
        const formData = new FormData();
        formData.append("file", idFile);
        await apiUpload(`/api/v1/clients/${client.id}/id-documents`, formData);
      }
      setCreateOpen(false);
      await load();
    } catch (err) {
      setError(err.message || "Failed to update client");
    } finally {
      setSaving(false);
    }
  }

  const relatedCases = useMemo(
    () => cases.filter((row) => Number(row.client_id) === Number(id)),
    [cases, id],
  );

  const relatedCaseIds = useMemo(
    () => new Set(relatedCases.map((row) => Number(row.id))),
    [relatedCases],
  );

  const relatedDocuments = useMemo(
    () => documents.filter((row) => row.case_id && relatedCaseIds.has(Number(row.case_id))),
    [documents, relatedCaseIds],
  );

  const relatedTasks = useMemo(
    () => tasks.filter((row) => row.case_id && relatedCaseIds.has(Number(row.case_id))),
    [tasks, relatedCaseIds],
  );

  const billingRows = useMemo(
    () => invoices.filter((row) => Number(row.client_id) === Number(id)),
    [invoices, id],
  );

  const overdueAmount = useMemo(
    () => billingRows.filter((row) => row.status === "overdue").reduce((sum, row) => sum + Number(row.balance_due || 0), 0),
    [billingRows],
  );

  const teamMap = useMemo(() => {
    const map = new Map();
    team.forEach((user) => map.set(Number(user.id), user));
    return map;
  }, [team]);

  const assignedTeam = useMemo(() => {
    const ids = new Set();
    relatedCases.forEach((row) => {
      (row.assigned_user_ids || []).forEach((uid) => ids.add(Number(uid)));
      if (row.lead_user_id) ids.add(Number(row.lead_user_id));
    });
    return Array.from(ids).map((uid) => teamMap.get(uid)).filter(Boolean);
  }, [relatedCases, teamMap]);

  const timelineRows = useMemo(() => {
    const caseRows = relatedCases.map((row) => ({
      id: `case-${row.id}`,
      title: row.title || `Case #${row.id}`,
      priority: row.priority || "medium",
      filing_date: row.filing_date || row.created_at,
      status: row.status || "active",
      type: "cases",
      href: `/dashboard/cases/${row.id}`,
    }));

    const taskRows = relatedTasks.map((row) => ({
      id: `task-${row.id}`,
      title: row.title || `Task #${row.id}`,
      priority: row.priority || "medium",
      filing_date: row.due_date || row.created_at,
      status: row.status || "pending",
      type: "notes",
      href: "/dashboard/tasks",
    }));

    const docsRows = relatedDocuments.map((row) => ({
      id: `doc-${row.id}`,
      title: row.title || row.file_name || `Document #${row.id}`,
      priority: "low",
      filing_date: row.created_at,
      status: "active",
      type: "documents",
      href: "/dashboard/documents",
    }));

    const notes = String(client?.notes || "")
      .split("\n")
      .filter((line) => line.trim() && !line.includes(":"))
      .slice(0, 4)
      .map((line, idx) => ({
        id: `note-${idx}`,
        title: line,
        priority: "medium",
        filing_date: client?.created_at,
        status: "active",
        type: "messages",
        href: "",
      }));

    let rows = [...caseRows, ...taskRows, ...docsRows, ...notes];

    if (timelineTab !== "all") rows = rows.filter((row) => row.type === timelineTab);
    if (timelineType !== "all") rows = rows.filter((row) => row.type === timelineType);

    if (timelineSearch.trim()) {
      const query = timelineSearch.toLowerCase();
      rows = rows.filter((row) => `${row.title} ${row.status} ${row.priority}`.toLowerCase().includes(query));
    }

    rows.sort((a, b) => {
      const left = new Date(a.filing_date || 0).getTime();
      const right = new Date(b.filing_date || 0).getTime();
      if (timelineOrder === "oldest") return left - right;
      return right - left;
    });

    return rows.slice(0, 6);
  }, [relatedCases, relatedTasks, relatedDocuments, client, timelineTab, timelineType, timelineOrder, timelineSearch]);

  const filteredDocuments = useMemo(() => {
    let rows = [...idDocuments];

    if (documentSearch.trim()) {
      const query = documentSearch.toLowerCase();
      rows = rows.filter((row) => `${row.title || ""} ${row.file_name || ""}`.toLowerCase().includes(query));
    }

    rows.sort((a, b) => {
      const left = new Date(a.created_at || 0).getTime();
      const right = new Date(b.created_at || 0).getTime();
      return documentOrder === "oldest" ? left - right : right - left;
    });

    return rows.slice(0, 8);
  }, [idDocuments, documentSearch, documentOrder]);

  async function removeIdDocument(documentId) {
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/clients/${id}/id-documents/${documentId}`, { method: "DELETE" });
      setDeleteDocumentId(null);
      await load();
    } catch (err) {
      setError(err.message || "Failed to delete document");
    } finally {
      setSaving(false);
    }
  }

  async function replaceIdDocument(e) {
    e.preventDefault();
    if (!replaceTarget || !replaceFile) {
      setError("Select a replacement file.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const formData = new FormData();
      formData.set("file", replaceFile);
      if (replaceNotes.trim()) formData.set("notes", replaceNotes.trim());
      await apiUpload(`/api/v1/documents/${replaceTarget.id}/replace`, formData);
      setReplaceTarget(null);
      setReplaceFile(null);
      setReplaceNotes("");
      await load();
    } catch (err) {
      setError(err.message || "Failed to replace document");
    } finally {
      setSaving(false);
    }
  }

  async function openVersionHistory(row) {
    setVersionTarget(row);
    setVersionRows([]);
    setError("");
    try {
      const rows = await apiRequest(`/api/v1/documents/${row.id}/versions`);
      setVersionRows(rows || []);
    } catch (err) {
      setError(err.message || "Failed to load versions");
    }
  }

  async function openDocumentPreview(row) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const name = String(row.file_name || "").toLowerCase();
    const ext = name.includes(".") ? name.split(".").pop() : "";
    if (ext === "doc" || ext === "docx") {
      setPreviewDoc({ ...row, previewType: "doc" });
      setPreviewUrl("");
      setPreviewError("");
      setPreviewLoading(false);
      return;
    }

    setPreviewDoc({ ...row, previewType: ext === "pdf" ? "pdf" : "image" });
    setPreviewLoading(true);
    setPreviewError("");
    setPreviewUrl("");
    try {
      const token = getToken();
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const response = await fetch(`${base}/api/v1/clients/${id}/id-documents/${row.id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error("Failed to load preview");
      const blob = await response.blob();
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (err) {
      setPreviewError(err.message || "Failed to load preview");
    } finally {
      setPreviewLoading(false);
    }
  }

  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    setPreviewError("");
    setPreviewLoading(false);
    setPreviewDoc(null);
  }

  if (loading) {
    return <section className="dashboard-page-stack"><p className="vilo-state vilo-state--loading">Loading client details...</p></section>;
  }

  if (error && !client) {
    return <section className="dashboard-page-stack"><p className="vilo-state vilo-state--error">{error}</p></section>;
  }

  const type = clientType(client);
  const trn = client?.trn_no || readMetaLine(client?.notes, "TRN No") || "-";
  const created = formatDate(client?.created_at);
  const dob = formatDate(client?.date_of_birth);
  const occupation = client?.occupation || "-";
  const preferredContact = client?.preferred_contact_method || readMetaLine(client?.notes, "Preferred Contact Method") || "-";
  const billingCurrency = client?.billing_currency || readMetaLine(client?.notes, "Billing Currency") || "USD";
  const statusLabel = client?.archived_at ? "Archived" : "Active";

  return (
    <section className="dashboard-page-stack client-detail-page">
      <div className="client-detail-top-row">
        <div>
          <h1>Client Details</h1>
          <p><Link href="/dashboard/clients">Clients</Link> &gt; Client Info</p>
        </div>
        <button type="button" className="vilo-btn vilo-btn--secondary client-create-split-btn" onClick={() => setCreateOpen(true)}>
          <span>+ Create</span>
          <span className="client-create-split-caret">⌄</span>
        </button>
      </div>

      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      <article className="dashboard-card client-identity-card">
        <div className="client-identity-main">
          <div className="client-avatar">{(client?.name || "C").slice(0, 1).toUpperCase()}</div>
          <div>
            <h2>{client?.name || "Client"}</h2>
            <p>CL-{String(client?.id || "").padStart(4, "0")} · {type} · {statusLabel}</p>
          </div>
        </div>
        <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs">•••</button>
      </article>

      <div className="client-detail-grid">
        <div className="client-detail-left">
          <article className="dashboard-card clients-list-card">
            <div className="dashboard-card__header"><h2>Client Timeline</h2></div>
            <div className="clients-tabs-row">
              {[
                ["all", "All"],
                ["notes", "Notes"],
                ["messages", "Messages"],
                ["documents", "Documents"],
                ["cases", "Cases"],
              ].map(([key, label]) => (
                <button key={key} type="button" className={timelineTab === key ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setTimelineTab(key)}>{label}</button>
              ))}
            </div>

            <div className="clients-toolbar-row client-detail-toolbar-row">
              <input className="case-search-input" placeholder="Search" value={timelineDraft} onChange={(e) => setTimelineDraft(e.target.value)} />
              <button className="vilo-btn vilo-btn--primary" type="button" onClick={() => setTimelineSearch(timelineDraft)}>Search</button>
              <div className="clients-select-wrap">
                <select value={timelineType} onChange={(e) => setTimelineType(e.target.value)}>
                  <option value="all">Type</option>
                  <option value="cases">Cases</option>
                  <option value="documents">Documents</option>
                  <option value="messages">Messages</option>
                  <option value="notes">Notes</option>
                </select>
              </div>
              <div className="clients-select-wrap">
                <select value={timelineOrder} onChange={(e) => setTimelineOrder(e.target.value)}>
                  <option value="newest">Last Modified</option>
                  <option value="oldest">Oldest First</option>
                </select>
              </div>
            </div>

            <div className="case-tab-panel" style={{ paddingTop: "0.5rem" }}>
              {timelineRows.length ? (
                <div className="vilo-table-wrap case-table-wrap">
                  <table className="team-table">
                    <thead>
                      <tr><th>Timeline</th><th>Priority</th><th>Filling Date</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                      {timelineRows.map((row) => (
                        <tr key={row.id}>
                          <td>{row.title}</td>
                          <td><span className={`vilo-badge vilo-badge--priority-${row.priority}`}>{row.priority}</span></td>
                          <td>{formatDate(row.filing_date)}</td>
                          <td><span className={`vilo-badge vilo-badge--${row.status}`}>{row.status}</span></td>
                          <td>{row.href ? <Link href={row.href}>View</Link> : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="vilo-state-block"><p className="vilo-state">No timeline data available for this filter.</p></div>
              )}
              <Link href="/dashboard/cases" className="client-view-all-link">View All Cases →</Link>
            </div>
          </article>

          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Billing</h2></div>
            {overdueAmount > 0 ? (
              <p className="vilo-card-copy">Overdue balance: <strong>${overdueAmount.toLocaleString()}</strong></p>
            ) : (
              <p className="vilo-card-copy">No overdue balance</p>
            )}
          </article>

          <article className="dashboard-card clients-list-card">
            <div className="dashboard-card__header"><h2>Documents</h2></div>
            <div className="clients-toolbar-row client-detail-toolbar-row">
              <input className="case-search-input" placeholder="Search" value={documentDraft} onChange={(e) => setDocumentDraft(e.target.value)} />
              <button className="vilo-btn vilo-btn--primary" type="button" onClick={() => setDocumentSearch(documentDraft)}>Search</button>
              <div className="clients-select-wrap clients-select-wrap--full">
                <select value={documentOrder} onChange={(e) => setDocumentOrder(e.target.value)}>
                  <option value="newest">Last Modified</option>
                  <option value="oldest">Oldest First</option>
                </select>
              </div>
            </div>

            <div className="case-tab-panel" style={{ paddingTop: "0.5rem" }}>
              {filteredDocuments.length ? (
                <div className="vilo-table-wrap case-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Name</th><th>Size</th><th>Last Modified</th><th>Actions</th></tr></thead>
                    <tbody>
                      {filteredDocuments.map((row) => (
                        <tr key={row.id}>
                          <td>{row.title || row.file_name || `Document #${row.id}`}</td>
                          <td>{row.file_size ? `${Math.ceil(row.file_size / 1024)} KB` : "-"}</td>
                          <td>{formatDate(row.created_at)}</td>
                          <td>
                            <div className="vilo-table-actions">
                              <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" type="button" onClick={() => openDocumentPreview(row)}>View</button>
                              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => apiDownload(`/api/v1/clients/${id}/id-documents/${row.id}/download`)}>Download</button>
                              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => setReplaceTarget(row)}>Edit / Replace</button>
                              <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => openVersionHistory(row)}>Versions</button>
                              <button className="vilo-btn vilo-btn--danger vilo-btn--xs" type="button" onClick={() => setDeleteDocumentId(row.id)}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="vilo-state-block"><p className="vilo-state">No documents found for this client.</p></div>
              )}
              <div className="case-pagination-row"><span>Showing {filteredDocuments.length} document entries</span></div>
            </div>
          </article>
        </div>

        <aside className="client-detail-right">
          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Client Overview</h2></div>
            <div className="client-overview-inner">
              <div className="client-overview-avatar">{(client?.name || "C").slice(0, 1).toUpperCase()}</div>
              <div className="client-overview-row"><span>TRN No:</span><strong>{trn}</strong></div>
              <div className="client-overview-row"><span>Status:</span><span className={`vilo-badge ${client?.archived_at ? "vilo-badge--archived" : "vilo-badge--active"}`}>{statusLabel}</span></div>
              <div className="client-overview-row"><span>Type:</span><span className="vilo-badge vilo-badge--priority-medium">{type}</span></div>
              {type === "Individual" ? <div className="client-overview-row"><span>Occupation:</span><strong>{occupation}</strong></div> : null}
              <div className="client-overview-row"><span>Preferred Contact:</span><strong>{preferredContact}</strong></div>
              <div className="client-overview-row"><span>Billing Currency:</span><strong>{billingCurrency}</strong></div>
              <div className="client-overview-row"><span>Date of Birth:</span><strong>{dob}</strong></div>
              <div className="client-overview-row"><span>Email:</span><strong>{client?.email || "-"}</strong></div>
              <div className="client-overview-row"><span>Phone:</span><strong>{client?.phone || "-"}</strong></div>
              <div className="client-overview-row"><span>Created:</span><strong>{created}</strong></div>
            </div>
          </article>

          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Assigned Team</h2></div>
            {assignedTeam.length ? (
              <div className="client-team-list">
                {assignedTeam.map((member) => (
                  <div key={member.id} className="client-team-row">
                    <span>{member.name}</span>
                    <span>›</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="vilo-card-copy">No assigned team members yet.</p>
            )}
            <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs">+ Add Member</button>
          </article>

          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Quick Actions</h2></div>
            <div className="client-quick-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => router.push("/dashboard/cases")}>Add Note</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => router.push("/dashboard/tasks")}>Add Task</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => router.push("/dashboard/messages")}>Send Message</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => router.push("/dashboard/cases")}>Create Case</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => router.push("/dashboard/reports")}>Add Time Entry</button>
            </div>
          </article>
        </aside>
      </div>

      <ClientIntakeModal
        open={createOpen}
        mode="edit"
        client={client}
        saving={saving}
        apiError={error}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleEdit}
      />

      {deleteDocumentId ? (
        <div className="vilo-modal-overlay" onClick={() => setDeleteDocumentId(null)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Delete ID Document</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setDeleteDocumentId(null)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <p>Delete this ID document? This cannot be undone.</p>
              <div className="vilo-table-actions">
                <button type="button" className="vilo-btn vilo-btn--danger" disabled={saving} onClick={() => removeIdDocument(deleteDocumentId)}>
                  {saving ? "Deleting..." : "Delete"}
                </button>
                <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => setDeleteDocumentId(null)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {previewDoc ? (
        <div className="vilo-modal-overlay" onClick={closePreview}>
          <div className="vilo-modal vilo-modal--doc-preview" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Document Preview</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={closePreview}>Close</button>
            </div>
            <div className="vilo-modal__body">
              {previewLoading ? <p className="vilo-state vilo-state--loading">Preparing preview...</p> : null}
              {previewError ? <p className="vilo-state vilo-state--error">{previewError}</p> : null}
              {!previewLoading && !previewError && previewDoc.previewType === "doc" ? (
                <div className="vilo-state-block">
                  <p className="vilo-state">Preview is not available for DOC/DOCX files. Use download to view this file.</p>
                </div>
              ) : null}
              {!previewLoading && !previewError && previewDoc.previewType === "image" && previewUrl ? (
                <img src={previewUrl} alt={previewDoc.file_name || "ID document"} className="client-doc-preview-image" />
              ) : null}
              {!previewLoading && !previewError && previewDoc.previewType === "pdf" && previewUrl ? (
                <iframe title={previewDoc.file_name || "PDF preview"} src={previewUrl} className="client-doc-preview-frame" />
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {replaceTarget ? (
        <div className="vilo-modal-overlay" onClick={() => { setReplaceTarget(null); setReplaceFile(null); setReplaceNotes(""); }}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Replace Document</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => { setReplaceTarget(null); setReplaceFile(null); setReplaceNotes(""); }}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <form className="vilo-form-grid" onSubmit={replaceIdDocument}>
                <p>Current file: <strong>{replaceTarget.file_name}</strong></p>
                <input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" onChange={(e) => setReplaceFile(e.target.files?.[0] || null)} required />
                <textarea placeholder="Version notes (optional)" value={replaceNotes} onChange={(e) => setReplaceNotes(e.target.value)} />
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => { setReplaceTarget(null); setReplaceFile(null); setReplaceNotes(""); }}>Cancel</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Replacing..." : "Replace Document"}</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      ) : null}

      {versionTarget ? (
        <div className="vilo-modal-overlay" onClick={() => setVersionTarget(null)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Version History</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setVersionTarget(null)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              {!versionRows.length ? <p className="vilo-state">No previous versions.</p> : null}
              {versionRows.length ? (
                <div className="vilo-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Version</th><th>File</th><th>Uploaded</th><th>Notes</th><th>Action</th></tr></thead>
                    <tbody>
                      {versionRows.map((row) => (
                        <tr key={row.id}>
                          <td>v{row.version_number}</td>
                          <td>{row.file_name}</td>
                          <td>{new Date(row.created_at).toLocaleString()}</td>
                          <td>{row.notes || "-"}</td>
                          <td><button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => apiDownload(`/api/v1/documents/${versionTarget.id}/versions/${row.id}/download`)}>Download</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
