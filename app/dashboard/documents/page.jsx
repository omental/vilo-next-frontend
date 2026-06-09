"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiDownload, apiRequest, apiUpload } from "../../../lib/api";
import { getToken } from "../../../lib/auth";

const initialForm = {
  case_id: "",
  title: "",
  description: "",
  category: "",
  file: null,
};

export default function DocumentsPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading documents...</p></div></section>}>
      <DocumentsPageContent />
    </Suspense>
  );
}

function DocumentsPageContent() {
  const searchParams = useSearchParams();
  const titleInputRef = useRef(null);
  const formCardRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [cases, setCases] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState(null);
  const [replaceFile, setReplaceFile] = useState(null);
  const [replaceNotes, setReplaceNotes] = useState("");
  const [versionTarget, setVersionTarget] = useState(null);
  const [versions, setVersions] = useState([]);
  const [success, setSuccess] = useState("");
  const [uploadOpen, setUploadOpen] = useState(searchParams.get("upload") === "1");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [docs, caseData] = await Promise.all([
        apiRequest("/api/v1/documents"),
        apiRequest("/api/v1/cases"),
      ]);
      setDocuments(docs);
      setCases(caseData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const shouldOpen = searchParams.get("upload") === "1";
    setUploadOpen(shouldOpen);
    if (!shouldOpen) return;
    formCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    titleInputRef.current?.focus();
  }, [searchParams]);

  async function uploadDocument(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!form.file) {
      setError("Please select a file to upload.");
      return;
    }

    const fd = new FormData();
    fd.append("title", form.title);
    if (form.description) fd.append("description", form.description);
    if (form.category) fd.append("category", form.category);
    if (form.case_id) fd.append("case_id", form.case_id);
    fd.append("file", form.file);

    const token = getToken();
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/v1/documents/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Upload failed");
      return;
    }

    setForm(initialForm);
    setUploadOpen(false);
    setSuccess("Document uploaded successfully.");
    await load();
  }

  async function replaceDocument(e) {
    e.preventDefault();
    if (!replaceTarget || !replaceFile) {
      setError("Select a replacement file.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", replaceFile);
      if (replaceNotes.trim()) fd.append("notes", replaceNotes.trim());
      await apiUpload(`/api/v1/documents/${replaceTarget.id}/replace`, fd);
      setReplaceTarget(null);
      setReplaceFile(null);
      setReplaceNotes("");
      await load();
    } catch (err) {
      setError(err.message || "Replace failed");
    } finally {
      setSaving(false);
    }
  }

  async function openVersions(document) {
    setVersionTarget(document);
    setVersions([]);
    setError("");
    try {
      const rows = await apiRequest(`/api/v1/documents/${document.id}/versions`);
      setVersions(rows || []);
    } catch (err) {
      setError(err.message || "Failed to load versions");
    }
  }

  async function deleteDocument(id) {
    await apiRequest(`/api/v1/documents/${id}`, { method: "DELETE" });
    await load();
  }

  function downloadDocument(id) {
    const token = getToken();
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    fetch(`${base}/api/v1/documents/${id}/download`, {
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

  function openReplaceModal(document) {
    setReplaceTarget(document);
    setReplaceFile(null);
    setReplaceNotes("");
    setSuccess("");
  }

  function closeReplaceModal() {
    setReplaceTarget(null);
    setReplaceFile(null);
    setReplaceNotes("");
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Documents</h1></div>

      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}

      <article ref={formCardRef} className="dashboard-card vilo-form-card vilo-collapsible-card">
        <div className="dashboard-card__header dashboard-card__header--action">
          <h2>Upload Document</h2>
          <button
            type="button"
            className={uploadOpen ? "vilo-btn vilo-btn--secondary vilo-btn--xs" : "vilo-btn vilo-btn--primary vilo-btn--xs"}
            aria-expanded={uploadOpen}
            onClick={() => {
              setUploadOpen((open) => !open);
              setSuccess("");
            }}
          >
            {uploadOpen ? "Hide Upload" : "Upload Document"}
          </button>
        </div>
        {uploadOpen ? (
          <form className="vilo-form-grid vilo-collapsible-card__body" onSubmit={uploadDocument}>
            <input ref={titleInputRef} placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="vilo-form-row-two">
              <input placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                <option value="">No linked case</option>
                {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </div>
            <input type="file" onChange={(e) => setForm({ ...form, file: e.target.files?.[0] || null })} required />
            <button type="submit">Upload</button>
          </form>
        ) : null}
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Document List</h2></div>
        {loading ? <p className="vilo-state">Loading documents...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error && documents.length === 0 ? <p className="vilo-state">No documents uploaded yet.</p> : null}
        {!loading && !error && documents.length > 0 ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Title</th><th>File</th><th>Case</th><th>Category</th><th>Actions</th></tr></thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id}>
                    <td>{d.title}</td>
                    <td>{d.file_name}</td>
                    <td>{d.case_id ? `#${d.case_id}` : "-"}</td>
                    <td>{d.category || "-"}</td>
                    <td>
                      <div className="vilo-table-actions">
                        <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => downloadDocument(d.id)}>Download</button>
                        <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => openReplaceModal(d)}>Edit / Replace</button>
                        <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => openVersions(d)}>Versions</button>
                        <button type="button" className="vilo-btn vilo-btn--danger vilo-btn--xs" onClick={() => deleteDocument(d.id)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>

      {replaceTarget ? (
        <div className="vilo-modal-overlay" onClick={closeReplaceModal}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Replace Document</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={closeReplaceModal}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <form className="vilo-form-grid" onSubmit={replaceDocument}>
                <p className="vilo-card-copy">Current file: <strong>{replaceTarget.file_name}</strong></p>
                <input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" onChange={(e) => setReplaceFile(e.target.files?.[0] || null)} required />
                <textarea placeholder="Version notes (optional)" value={replaceNotes} onChange={(e) => setReplaceNotes(e.target.value)} />
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeReplaceModal}>Cancel</button>
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
              {!versions.length ? <p className="vilo-state">No previous versions.</p> : null}
              {versions.length ? (
                <div className="vilo-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Version</th><th>File</th><th>Uploaded</th><th>Notes</th><th>Action</th></tr></thead>
                    <tbody>
                      {versions.map((v) => (
                        <tr key={v.id}>
                          <td>v{v.version_number}</td>
                          <td>{v.file_name}</td>
                          <td>{new Date(v.created_at).toLocaleString()}</td>
                          <td>{v.notes || "-"}</td>
                          <td><button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => apiDownload(`/api/v1/documents/${versionTarget.id}/versions/${v.id}/download`)}>Download</button></td>
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
