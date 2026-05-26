"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const inviteInitial = { email: "", role: "lawyer" };
const editInitial = { id: null, role: "lawyer", status: "active" };

export default function TeamPage() {
  const [team, setTeam] = useState([]);
  const [invites, setInvites] = useState([]);
  const [inviteForm, setInviteForm] = useState(inviteInitial);
  const [editForm, setEditForm] = useState(editInitial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadAll() {
    setLoading(true);
    setError("");
    try {
      const [users, inviteRows] = await Promise.all([
        apiRequest("/api/v1/admin/users"),
        apiRequest("/api/v1/admin/invites"),
      ]);
      setTeam(users);
      setInvites(inviteRows);
    } catch (err) {
      setError(err.message || "Failed to load team data");
      setTeam([]);
      setInvites([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function sendInvite(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/v1/admin/invites", {
        method: "POST",
        body: JSON.stringify(inviteForm),
      });
      setInviteForm(inviteInitial);
      await loadAll();
    } catch (err) {
      setError(err.message || "Invite failed");
    } finally {
      setSaving(false);
    }
  }

  async function resendInvite(id) {
    try {
      await apiRequest(`/api/v1/admin/invites/${id}/resend`, { method: "POST" });
      await loadAll();
    } catch (err) {
      setError(err.message || "Resend failed");
    }
  }

  async function cancelInvite(id) {
    if (!confirm("Cancel this invite?")) return;
    try {
      await apiRequest(`/api/v1/admin/invites/${id}/cancel`, { method: "POST" });
      await loadAll();
    } catch (err) {
      setError(err.message || "Cancel failed");
    }
  }

  async function saveUserEdit(e) {
    e.preventDefault();
    if (!editForm.id) return;
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/api/v1/admin/users/${editForm.id}`, {
        method: "PATCH",
        body: JSON.stringify({ role: editForm.role, status: editForm.status }),
      });
      setEditForm(editInitial);
      await loadAll();
    } catch (err) {
      setError(err.message || "Update failed");
    } finally {
      setSaving(false);
    }
  }

  async function deactivateUser(id) {
    if (!confirm("Deactivate this user?")) return;
    try {
      await apiRequest(`/api/v1/admin/users/${id}`, { method: "DELETE" });
      await loadAll();
    } catch (err) {
      setError(err.message || "Deactivate failed");
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Team</h1></div>
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Invite Team Member</h2></div>
        <form className="vilo-form-row-two" onSubmit={sendInvite}>
          <input type="email" placeholder="Email" value={inviteForm.email} onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })} required />
          <select value={inviteForm.role} onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}>
            <option value="partner">partner</option>
            <option value="admin">admin</option>
            <option value="lawyer">lawyer</option>
            <option value="paralegal">paralegal</option>
          </select>
          <button type="submit" disabled={saving}>{saving ? "Sending..." : "Send Invite"}</button>
        </form>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Organization Team</h2></div>
        {loading ? <p className="vilo-state">Loading team...</p> : null}
        {!loading ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {team.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td><span className={`vilo-badge vilo-badge--priority-${u.role}`}>{u.role}</span></td>
                    <td><span className={`vilo-badge vilo-badge--${u.status === "active" ? "completed" : "cancelled"}`}>{u.status}</span></td>
                    <td>
                      <button onClick={() => setEditForm({ id: u.id, role: u.role, status: u.status })}>Edit</button>
                      <button onClick={() => deactivateUser(u.id)} style={{ marginLeft: 8 }}>Deactivate</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>

      {editForm.id ? (
        <article className="dashboard-card vilo-form-card">
          <div className="dashboard-card__header"><h2>Edit User #{editForm.id}</h2></div>
          <form className="vilo-form-row-two" onSubmit={saveUserEdit}>
            <select value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
              <option value="partner">partner</option>
              <option value="admin">admin</option>
              <option value="lawyer">lawyer</option>
              <option value="paralegal">paralegal</option>
              <option value="client">client</option>
            </select>
            <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</button>
            <button type="button" onClick={() => setEditForm(editInitial)}>Cancel</button>
          </form>
        </article>
      ) : null}

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Invites</h2></div>
        {loading ? <p className="vilo-state">Loading invites...</p> : null}
        {!loading && !invites.length ? <p className="vilo-state">No invites yet.</p> : null}
        {!loading && invites.length ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Expires</th><th>Actions</th></tr></thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.email}</td>
                    <td>{inv.role}</td>
                    <td>{inv.status}</td>
                    <td>{new Date(inv.expires_at).toLocaleString()}</td>
                    <td>
                      <button onClick={() => resendInvite(inv.id)}>Resend</button>
                      <button onClick={() => cancelInvite(inv.id)} style={{ marginLeft: 8 }}>Cancel</button>
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
