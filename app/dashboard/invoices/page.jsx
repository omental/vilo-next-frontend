"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiDownload, apiRequest } from "../../../lib/api";

const initialForm = {
  client_id: "",
  case_id: "",
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: "",
  notes: "",
};

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function InvoicesPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading invoices...</p></div></section>}>
      <InvoicesPageContent />
    </Suspense>
  );
}

function InvoicesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [createError, setCreateError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(initialForm);
  const requestedClientId = searchParams.get("client_id") || "";

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [invoiceRows, clientRows, caseRows] = await Promise.all([
        apiRequest("/api/v1/invoices"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/cases").catch(() => []),
      ]);
      setItems(invoiceRows || []);
      setClients(clientRows || []);
      setCases(caseRows || []);
    } catch (err) {
      setError(err.message || "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    const nextClientId = searchParams.get("client_id") || "";
    setForm((current) => {
      if (current.client_id === nextClientId) return current;
      return { ...current, client_id: nextClientId, case_id: "" };
    });
  }, [searchParams]);

  const selectedClientId = Number(form.client_id || 0);
  const caseOptions = useMemo(() => {
    if (!selectedClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === selectedClientId);
  }, [cases, selectedClientId]);

  const totals = useMemo(() => ({
    balance: items.reduce((sum, row) => sum + Number(row.balance_due || 0), 0),
    drafts: items.filter((row) => row.status === "draft").length,
    sent: items.filter((row) => row.status === "sent").length,
  }), [items]);

  function openCreateModal() {
    setCreateError("");
    setForm({ ...initialForm, client_id: requestedClientId });
    setCreateOpen(true);
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setCreateError("");
    setForm({ ...initialForm, client_id: requestedClientId });
    if (searchParams.get("create") === "1") {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("create");
      const next = params.toString();
      router.replace(next ? `/dashboard/invoices?${next}` : "/dashboard/invoices");
    }
  }

  async function markSent(id) {
    setError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-sent`, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to mark invoice as sent");
    }
  }

  async function markPaid(id) {
    setError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-paid`, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to mark invoice as paid");
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.client_id || !form.issue_date) {
      setCreateError("Client and issue date are required.");
      return;
    }

    setSaving(true);
    setCreateError("");
    try {
      const created = await apiRequest("/api/v1/invoices", {
        method: "POST",
        body: JSON.stringify({
          client_id: Number(form.client_id),
          case_id: form.case_id ? Number(form.case_id) : null,
          issue_date: form.issue_date,
          due_date: form.due_date || null,
          notes: form.notes.trim() || null,
        }),
      });
      closeCreateModal();
      await load();
      router.push(`/dashboard/invoices/${created.id}`);
    } catch (err) {
      setCreateError(err.message || "Failed to create invoice");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="invoice-page-top-row">
        <div className="dashboard-page-heading">
          <h1>Invoices</h1>
          <p className="invoice-page-intro">Create, review, and export firm invoices from one place.</p>
        </div>
        <div className="invoice-page-actions">
          <Link className="vilo-btn vilo-btn--secondary" href="/dashboard/billing">Billing Hub</Link>
          <button type="button" className="vilo-btn vilo-btn--primary" onClick={openCreateModal} disabled={!clients.length && !loading}>Create Invoice</button>
        </div>
      </div>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      <div className="invoice-summary-grid">
        <article className="dashboard-card invoice-summary-card">
          <span>Total Invoices</span>
          <strong>{items.length}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Drafts</span>
          <strong>{totals.drafts}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Sent</span>
          <strong>{totals.sent}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Outstanding</span>
          <strong>{formatMoney(totals.balance)}</strong>
        </article>
      </div>

      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading invoices...</p></div> : null}

      {!loading && !clients.length ? (
        <div className="vilo-state-block">
          <p className="vilo-state">Create at least one client before creating an invoice.</p>
        </div>
      ) : null}

      {!loading && !error && !items.length ? (
        <div className="vilo-state-block">
          <p className="vilo-state">No invoices found yet. Use Create Invoice to start the MVP billing flow.</p>
        </div>
      ) : null}

      {!loading && !error && items.length ? (
        <article className="dashboard-card vilo-table-card">
          <div className="dashboard-card__header"><h2>Invoice List</h2></div>
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Issue Date</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Balance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.invoice_number}</td>
                    <td>{row.client?.name || `Client #${row.client_id}`}</td>
                    <td>{formatDate(row.issue_date)}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td><span className={`vilo-badge vilo-badge--${row.status}`}>{row.status}</span></td>
                    <td>{formatMoney(row.total)}</td>
                    <td>{formatMoney(row.balance_due)}</td>
                    <td>
                      <div className="vilo-table-actions">
                        <Link className="vilo-btn vilo-btn--secondary vilo-btn--xs" href={`/dashboard/invoices/${row.id}`}>View</Link>
                        <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => apiDownload(`/api/v1/invoices/${row.id}/pdf`)}>PDF</button>
                        {row.status === "draft" ? <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" type="button" onClick={() => markSent(row.id)}>Mark sent</button> : null}
                        {row.status !== "paid" ? <button className="vilo-btn vilo-btn--primary vilo-btn--xs" type="button" onClick={() => markPaid(row.id)}>Mark paid</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}

      {createOpen ? (
        <div className="vilo-modal-overlay" onClick={closeCreateModal}>
          <div className="vilo-modal invoice-create-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <div>
                <h3>Create Invoice</h3>
                <p className="invoice-modal-copy">This uses the existing invoice API and opens the invoice detail view after save.</p>
              </div>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={closeCreateModal}>Close</button>
            </div>
            <form className="vilo-modal__body invoice-create-form" onSubmit={handleCreate}>
              <div className="vilo-form-row-two">
                <div>
                  <label>Client *</label>
                  <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value, case_id: "" })} required>
                    <option value="">Select client</option>
                    {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                </div>
                <div>
                  <label>Case</label>
                  <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                    <option value="">No case</option>
                    {caseOptions.map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
                  </select>
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Issue Date *</label>
                  <input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} required />
                </div>
                <div>
                  <label>Due Date</label>
                  <input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
                </div>
              </div>

              <div>
                <label>Notes</label>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Optional invoice notes" />
              </div>

              {createError ? <p className="vilo-state vilo-state--error">{createError}</p> : null}

              <div className="vilo-table-actions invoice-create-actions">
                <button className="vilo-btn vilo-btn--secondary" type="button" onClick={closeCreateModal}>Cancel</button>
                <button className="vilo-btn vilo-btn--primary" type="submit" disabled={saving}>{saving ? "Creating..." : "Create Invoice"}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
