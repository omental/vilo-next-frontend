"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getCachedUser, setCachedUser } from "../../../lib/auth";
import { apiDownload, apiRequest } from "../../../lib/api";

const LINE_ITEM_TYPE_OPTIONS = [
  ["legal_fee", "Legal Fee"],
  ["hourly_work", "Hourly Work"],
  ["flat_fee", "Flat Fee"],
  ["disbursement", "Disbursement"],
  ["expense", "Expense"],
  ["approved_billable_expense", "Approved Billable Expense"],
];

const initialForm = {
  client_id: "",
  case_id: "",
  invoice_number: "",
  currency: "USD",
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: "",
  tax_amount: "",
  notes: "",
  payment_instructions: "",
  line_items: [
    { line_type: "legal_fee", description: "", quantity: "1", unit_price: "", amount: "" },
  ],
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

function roleCanManagePayments(role) {
  return role === "partner" || role === "admin";
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
  const [currentUser, setCurrentUser] = useState(getCachedUser());
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
  const requestedCaseId = searchParams.get("case_id") || "";

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
    if (currentUser) return;
    let cancelled = false;
    apiRequest("/api/v1/auth/me")
      .then((me) => {
        if (cancelled) return;
        setCurrentUser(me);
        setCachedUser(me);
      })
      .catch(() => {
        if (cancelled) return;
        setCurrentUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    const nextClientId = searchParams.get("client_id") || "";
    const nextCaseId = searchParams.get("case_id") || "";
    setForm((current) => ({ ...current, client_id: nextClientId, case_id: nextCaseId }));
  }, [searchParams]);

  useEffect(() => {
    if (!requestedCaseId || !cases.length) return;
    const caseRow = cases.find((row) => Number(row.id) === Number(requestedCaseId));
    if (!caseRow) return;
    setForm((current) => ({
      ...current,
      case_id: current.case_id || String(caseRow.id),
      client_id: current.client_id || String(caseRow.client_id),
    }));
  }, [cases, requestedCaseId]);

  const selectedClientId = Number(form.client_id || 0);
  const caseOptions = useMemo(() => {
    if (!selectedClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === selectedClientId);
  }, [cases, selectedClientId]);

  const totals = useMemo(() => ({
    balance: items.reduce((sum, row) => sum + Number(row.balance_due || 0), 0),
    drafts: items.filter((row) => row.status === "draft").length,
    sent: items.filter((row) => ["sent", "partially_paid"].includes(row.display_status || row.status)).length,
    overdue: items.filter((row) => (row.display_status || row.status) === "overdue").length,
  }), [items]);
  const canManagePayments = roleCanManagePayments(currentUser?.role || "");

  function openCreateModal() {
    setCreateError("");
    setForm({ ...initialForm, client_id: requestedClientId, case_id: requestedCaseId });
    setCreateOpen(true);
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setCreateError("");
    setForm({ ...initialForm, client_id: requestedClientId, case_id: requestedCaseId });
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
    if (!form.client_id || !form.case_id || !form.issue_date) {
      setCreateError("Client, matter, and issue date are required.");
      return;
    }
    const cleanLineItems = form.line_items
      .filter((row) => row.description.trim() && row.unit_price !== "")
      .map((row) => ({
        line_type: row.line_type,
        description: row.description.trim(),
        quantity: Number(row.quantity || 0),
        unit_price: Number(row.unit_price || 0),
        amount: row.amount !== "" ? Number(row.amount) : null,
      }));

    setSaving(true);
    setCreateError("");
    try {
      const created = await apiRequest("/api/v1/invoices", {
        method: "POST",
        body: JSON.stringify({
          client_id: Number(form.client_id),
          case_id: Number(form.case_id),
          invoice_number: form.invoice_number.trim() || null,
          currency: form.currency,
          issue_date: form.issue_date,
          due_date: form.due_date || null,
          tax_amount: form.tax_amount !== "" ? Number(form.tax_amount) : 0,
          notes: form.notes.trim() || null,
          payment_instructions: form.payment_instructions.trim() || null,
          line_items: cleanLineItems,
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
          <p className="invoice-page-intro">Create, review, and collect earned-fee invoices while keeping trust funds separate until applied.</p>
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
          <span>Sent / Partial</span>
          <strong>{totals.sent}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Overdue</span>
          <strong>{totals.overdue}</strong>
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
                  <th>Matter</th>
                  <th>Issue Date</th>
                  <th>Due Date</th>
                  <th>Status</th>
                  <th>Payment Method</th>
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
                    <td>{row.matter_title || (row.case_id ? `Matter #${row.case_id}` : "-")}</td>
                    <td>{formatDate(row.issue_date)}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td><span className={`vilo-badge vilo-badge--${row.display_status || row.status}`}>{row.display_status || row.status}</span></td>
                    <td>{row.payment_method_summary}</td>
                    <td>{formatMoney(row.total, row.currency || "USD")}</td>
                    <td>{formatMoney(row.balance_due, row.currency || "USD")}</td>
                    <td>
                      <div className="vilo-table-actions">
                        <Link className="vilo-btn vilo-btn--secondary vilo-btn--xs" href={`/dashboard/invoices/${row.id}`}>View</Link>
                        <button className="vilo-btn vilo-btn--ghost vilo-btn--xs" type="button" onClick={() => apiDownload(`/api/v1/invoices/${row.id}/pdf`)}>PDF</button>
                        {row.status === "draft" ? <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" type="button" onClick={() => markSent(row.id)}>Send invoice</button> : null}
                        {canManagePayments && (row.display_status || row.status) !== "paid" && (row.display_status || row.status) !== "cancelled" ? <button className="vilo-btn vilo-btn--primary vilo-btn--xs" type="button" onClick={() => markPaid(row.id)}>Record Direct Payment</button> : null}
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
                <p className="invoice-modal-copy">Firm billing only. Billable/legal line items belong here; trust deposits and client funds do not.</p>
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
                  <label>Matter / Case *</label>
                  <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })} required>
                    <option value="">Select matter</option>
                    {caseOptions.map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
                  </select>
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Invoice Number</label>
                  <input value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} placeholder="Auto-generate if blank" />
                </div>
                <div>
                  <label>Currency *</label>
                  <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} required>
                    <option value="USD">USD</option>
                    <option value="JMD">JMD</option>
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

              <div className="vilo-form-row-two">
                <div>
                  <label>GCT / Tax</label>
                  <input type="number" step="0.01" min="0" value={form.tax_amount} onChange={(e) => setForm({ ...form, tax_amount: e.target.value })} placeholder="0.00" />
                </div>
                <div>
                  <label>Payment Instructions</label>
                  <input value={form.payment_instructions} onChange={(e) => setForm({ ...form, payment_instructions: e.target.value })} placeholder="Bank transfer, cheque, office payment..." />
                </div>
              </div>

              <div className="invoice-line-items-editor">
                <div className="invoice-line-items-editor__header">
                  <div>
                    <label>Billable / Legal Line Items Only</label>
                    <p className="invoice-modal-copy">Trust deposits, retainers held in trust, escrow, and client funds are excluded by design.</p>
                  </div>
                  <button
                    type="button"
                    className="vilo-btn vilo-btn--secondary vilo-btn--xs"
                    onClick={() => setForm((current) => ({
                      ...current,
                      line_items: [...current.line_items, { line_type: "legal_fee", description: "", quantity: "1", unit_price: "", amount: "" }],
                    }))}
                  >
                    Add line item
                  </button>
                </div>
                {form.line_items.map((item, index) => (
                  <div className="invoice-line-item-row" key={`line-${index}`}>
                    <select value={item.line_type} onChange={(e) => setForm((current) => {
                      const next = [...current.line_items];
                      next[index] = { ...next[index], line_type: e.target.value };
                      return { ...current, line_items: next };
                    })}>
                      {LINE_ITEM_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <input value={item.description} onChange={(e) => setForm((current) => {
                      const next = [...current.line_items];
                      next[index] = { ...next[index], description: e.target.value };
                      return { ...current, line_items: next };
                    })} placeholder="Description" />
                    <input type="number" step="0.01" min="0.01" value={item.quantity} onChange={(e) => setForm((current) => {
                      const next = [...current.line_items];
                      next[index] = { ...next[index], quantity: e.target.value };
                      return { ...current, line_items: next };
                    })} placeholder="Qty" />
                    <input type="number" step="0.01" min="0" value={item.unit_price} onChange={(e) => setForm((current) => {
                      const next = [...current.line_items];
                      next[index] = { ...next[index], unit_price: e.target.value };
                      return { ...current, line_items: next };
                    })} placeholder="Unit price" />
                    <input type="number" step="0.01" min="0" value={item.amount} onChange={(e) => setForm((current) => {
                      const next = [...current.line_items];
                      next[index] = { ...next[index], amount: e.target.value };
                      return { ...current, line_items: next };
                    })} placeholder="Amount override" />
                    <button
                      type="button"
                      className="vilo-btn vilo-btn--ghost vilo-btn--xs"
                      onClick={() => setForm((current) => ({
                        ...current,
                        line_items: current.line_items.length === 1 ? current.line_items : current.line_items.filter((_, rowIndex) => rowIndex !== index),
                      }))}
                    >
                      Remove
                    </button>
                  </div>
                ))}
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
