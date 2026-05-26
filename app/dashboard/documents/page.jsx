"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";
import { getToken } from "../../../lib/auth";

const initialForm = {
  case_id: "",
  title: "",
  description: "",
  category: "",
  file: null,
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [cases, setCases] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  async function uploadDocument(e) {
    e.preventDefault();
    setError("");
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
    await load();
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

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Documents</h1></div>

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Upload Document</h2></div>
        <form className="vilo-form-grid" onSubmit={uploadDocument}>
          <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
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
                      <button onClick={() => downloadDocument(d.id)}>Download</button>
                      <button onClick={() => deleteDocument(d.id)} style={{ marginLeft: 8 }}>Delete</button>
                    </td>
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
