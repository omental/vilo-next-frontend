"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../../../lib/api";
import { getCachedUser } from "../../../lib/auth";
import { DiscardChangesDialog, useModalCloseGuard } from "../../../components/useModalCloseGuard";

const createInitial = {
  name: "",
  email: "",
  password: "",
  confirmPassword: "",
  role: "lawyer",
  status: "active",
};
const editInitial = { id: null, role: "lawyer", status: "active" };
const ROLE_OPTIONS = ["partner", "admin", "lawyer", "paralegal"];

export default function TeamPage() {
  const [team, setTeam] = useState([]);
  const [createForm, setCreateForm] = useState(createInitial);
  const [editForm, setEditForm] = useState(editInitial);
  const [addOpen, setAddOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const currentUser = useMemo(() => getCachedUser(), []);
  const canManageTeam = ["partner", "admin"].includes(String(currentUser?.role || "").toLowerCase());

  async function loadAll() {
    setLoading(true);
    setError("");
    try {
      const users = await apiRequest("/api/v1/admin/users");
      setTeam(users);
    } catch (err) {
      setError(err.message || "Failed to load team data");
      setTeam([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function closeAddModal() {
    setAddOpen(false);
    setCreateForm(createInitial);
  }

  async function createUser(e) {
    e.preventDefault();
    if (saving) return;
    setError("");
    setSuccess("");

    if (createForm.password !== createForm.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setSaving(true);
    try {
      await apiRequest("/api/v1/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name: createForm.name,
          email: createForm.email,
          password: createForm.password,
          role: createForm.role,
          status: createForm.status,
        }),
      });
      setSuccess("Team member created successfully.");
      closeAddModal();
      await loadAll();
    } catch (err) {
      setError(err.message || "Team member creation failed");
    } finally {
      setSaving(false);
    }
  }

  async function saveUserEdit(e) {
    e.preventDefault();
    if (!editForm.id || saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest(`/api/v1/admin/users/${editForm.id}`, {
        method: "PATCH",
        body: JSON.stringify({ role: editForm.role, status: editForm.status }),
      });
      setEditForm(editInitial);
      setSuccess("Team member updated.");
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
      setSuccess("Team member deactivated.");
      await loadAll();
    } catch (err) {
      setError(err.message || "Deactivate failed");
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading dashboard-page-heading--split">
        <h1>Team</h1>
        {canManageTeam ? (
          <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => { setError(""); setSuccess(""); setAddOpen(true); }}>
            Add Team Member
          </button>
        ) : null}
      </div>
      {success ? <p className="vilo-state">{success}</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

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
              {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
              <option value="client">client</option>
            </select>
            <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</button>
            <button type="button" onClick={() => setEditForm(editInitial)} disabled={saving}>Cancel</button>
          </form>
        </article>
      ) : null}

      {addOpen ? (
        <TeamMemberModal
          form={createForm}
          setForm={setCreateForm}
          saving={saving}
          error={error}
          onClose={closeAddModal}
          onSubmit={createUser}
        />
      ) : null}
    </section>
  );
}

function TeamMemberModal({ form, setForm, saving, error, onClose, onSubmit }) {
  const dirty = JSON.stringify(form) !== JSON.stringify(createInitial);
  const closeGuard = useModalCloseGuard({ open: true, isDirty: dirty, isSubmitting: saving, onClose });

  return (
    <div className="vilo-modal-overlay" onClick={closeGuard.requestClose}>
      <div className="vilo-modal" onClick={(event) => event.stopPropagation()}>
        <div className="vilo-modal__header">
          <h3>Add Team Member</h3>
          <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={closeGuard.requestClose} disabled={saving}>Close</button>
        </div>
        <form className="vilo-modal__body vilo-form-grid" onSubmit={onSubmit}>
          <input placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <div className="vilo-form-row-two">
            <input type="password" placeholder="Initial password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength={8} required />
            <input type="password" placeholder="Confirm password" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} minLength={8} required />
          </div>
          <div className="vilo-form-row-two">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
            </select>
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </div>
          {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
          <div className="vilo-table-actions">
            <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeGuard.requestClose} disabled={saving}>Cancel</button>
            <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Creating..." : "Create Team Member"}</button>
          </div>
        </form>
      </div>
      <DiscardChangesDialog open={closeGuard.confirmDiscard} onKeepEditing={closeGuard.keepEditing} onDiscard={closeGuard.discard} />
    </div>
  );
}
