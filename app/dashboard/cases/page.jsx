"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  title: "",
  description: "",
  client_id: "",
  status: "draft",
  priority: "medium",
  assigned_user_ids: [],
};

export default function CasesPage() {
  const [cases, setCases] = useState([]);
  const [clients, setClients] = useState([]);
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [caseData, clientData, teamData] = await Promise.all([
        apiRequest("/api/v1/cases"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/team"),
      ]);
      setCases(caseData);
      setClients(clientData);
      setTeam(teamData.filter((u) => u.role !== "client"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createCase(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          client_id: Number(form.client_id),
        }),
      });
      setForm(initialForm);
      await load();
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

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Cases</h1></div>

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Create Case</h2></div>
        <form className="vilo-form-grid" onSubmit={createCase}>
          <input placeholder="Case title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
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
            <p>Assign users</p>
            {team.map((user) => (
              <label key={user.id}>
                <input
                  type="checkbox"
                  checked={form.assigned_user_ids.includes(user.id)}
                  onChange={() => toggleUser(user.id)}
                />
                {user.name} ({user.role})
              </label>
            ))}
          </div>

          <button type="submit" disabled={saving}>{saving ? "Creating..." : "Create Case"}</button>
        </form>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Case List</h2></div>
        {loading ? <p className="vilo-state">Loading cases...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error && cases.length === 0 ? <p className="vilo-state">No cases yet. Create one above.</p> : null}

        {!loading && !error && cases.length > 0 ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr><th>Title</th><th>Status</th><th>Priority</th><th>Client</th><th>Action</th></tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id}>
                    <td>{c.title}</td>
                    <td><span className={`vilo-badge vilo-badge--${c.status}`}>{c.status}</span></td>
                    <td><span className={`vilo-badge vilo-badge--priority-${c.priority}`}>{c.priority}</span></td>
                    <td>#{c.client_id}</td>
                    <td><Link href={`/dashboard/cases/${c.id}`}>View case</Link></td>
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
