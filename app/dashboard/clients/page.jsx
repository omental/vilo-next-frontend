"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const initialForm = { name: "", email: "", phone: "", address: "", notes: "" };

export default function ClientsPage() {
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/api/v1/clients");
      setClients(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createClient(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/v1/clients", { method: "POST", body: JSON.stringify(form) });
      setForm(initialForm);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Clients</h1></div>

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Add Client</h2></div>
        <form className="vilo-form-grid" onSubmit={createClient}>
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <input placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          <textarea placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="submit" disabled={saving}>{saving ? "Saving..." : "Add Client"}</button>
        </form>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Client List</h2></div>
        {loading ? <p className="vilo-state">Loading clients...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error && clients.length === 0 ? <p className="vilo-state">No clients yet. Add your first client above.</p> : null}

        {!loading && !error && clients.length > 0 ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr><th>Name</th><th>Email</th><th>Phone</th><th>Action</th></tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr key={client.id}>
                    <td>{client.name}</td>
                    <td>{client.email || "-"}</td>
                    <td>{client.phone || "-"}</td>
                    <td><Link href={`/dashboard/clients/${client.id}`}>View details</Link></td>
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
