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
  payment_account_id: "",
  line_items: [
    { line_type: "legal_fee", description: "", quantity: "1", unit_price: "", amount: "", time_entry_id: null },
  ],
};

function formatMoney(value, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value || 0));
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

function makeManualLineItem() {
  return { line_type: "legal_fee", description: "", quantity: "1", unit_price: "", amount: "", time_entry_id: null };
}

function resolveDefaultPaymentAccount(accounts, currency) {
  return (accounts || []).find((account) => account.currency === currency && account.is_default && account.is_active)
    || (accounts || []).find((account) => account.currency === currency && account.is_active)
    || null;
}

function createTimeEntryLine(entry) {
  return {
    line_type: "hourly_work",
    description: entry.description || "Time entry",
    quantity: String(entry.duration_minutes ? Number(entry.duration_minutes) / 60 : 0),
    unit_price: String(entry.hourly_rate || 0),
    amount: String(entry.amount || 0),
    time_entry_id: entry.id,
    hours: entry.duration_minutes ? (Number(entry.duration_minutes) / 60).toFixed(2) : "0.00",
    rate: String(entry.hourly_rate || 0),
    staff_name: entry.staff_name || "Staff",
    currency: entry.currency || "USD",
  };
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
  const [paymentAccounts, setPaymentAccounts] = useState([]);
  const [billableEntries, setBillableEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadingTimeEntries, setLoadingTimeEntries] = useState(false);
  const [error, setError] = useState("");
  const [createError, setCreateError] = useState("");
  const [timeEntryError, setTimeEntryError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(initialForm);
  const requestedClientId = searchParams.get("client_id") || "";
  const requestedCaseId = searchParams.get("case_id") || "";

  const filteredPaymentAccounts = useMemo(
    () => (paymentAccounts || []).filter((account) => account.currency === form.currency && account.is_active),
    [form.currency, paymentAccounts],
  );
  const selectedPaymentAccount = useMemo(
    () => filteredPaymentAccounts.find((account) => Number(account.id) === Number(form.payment_account_id || 0)) || null,
    [filteredPaymentAccounts, form.payment_account_id],
  );
  const paymentAccountWarning = !filteredPaymentAccounts.length
    ? "No payment account configured for this currency. Add one in Settings."
    : "";
  const selectedClientId = Number(form.client_id || 0);
  const caseOptions = useMemo(() => {
    if (!selectedClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === selectedClientId);
  }, [cases, selectedClientId]);
  const availableBillableEntries = useMemo(
    () => (billableEntries || []).filter((entry) => (entry.currency || "USD") === form.currency),
    [billableEntries, form.currency],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [invoiceRows, clientRows, caseRows, accountRows] = await Promise.all([
        apiRequest("/api/v1/invoices"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/cases").catch(() => []),
        apiRequest("/api/v1/settings/payment-accounts").catch(() => []),
      ]);
      setItems(invoiceRows || []);
      setClients(clientRows || []);
      setCases(caseRows || []);
      setPaymentAccounts(accountRows || []);
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
    if (searchParams.get("create") === "1") setCreateOpen(true);
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

  useEffect(() => {
    const defaultAccount = resolveDefaultPaymentAccount(paymentAccounts, form.currency);
    setForm((current) => {
      const currentStillValid = (paymentAccounts || []).some(
        (account) => Number(account.id) === Number(current.payment_account_id || 0) && account.currency === current.currency && account.is_active,
      );
      if (currentStillValid) return current;
      return {
        ...current,
        payment_account_id: defaultAccount ? String(defaultAccount.id) : "",
        payment_instructions: defaultAccount?.payment_instructions || current.payment_instructions || "",
      };
    });
  }, [form.currency, paymentAccounts]);

  useEffect(() => {
    if (!createOpen || !form.case_id) {
      setBillableEntries([]);
      return;
    }
    let cancelled = false;
    async function loadBillableEntries() {
      setLoadingTimeEntries(true);
      setTimeEntryError("");
      try {
        const rows = await apiRequest(`/api/v1/time-entries?case_id=${form.case_id}&status=billable&page=1&per_page=100&sort_by=newest`);
        if (cancelled) return;
        const selectedIds = new Set((form.line_items || []).map((item) => item.time_entry_id).filter(Boolean));
        setBillableEntries((rows.items || []).filter((entry) => !selectedIds.has(entry.id)));
      } catch (err) {
        if (cancelled) return;
        setTimeEntryError(err.message || "Failed to load billable time entries.");
      } finally {
        if (!cancelled) setLoadingTimeEntries(false);
      }
    }
    loadBillableEntries();
    return () => {
      cancelled = true;
    };
  }, [createOpen, form.case_id, form.line_items]);

  const totals = useMemo(() => ({
    balance: items.reduce((sum, row) => sum + Number(row.balance_due || 0), 0),
    drafts: items.filter((row) => row.status === "draft").length,
    sent: items.filter((row) => ["sent", "partially_paid"].includes(row.display_status || row.status)).length,
    overdue: items.filter((row) => (row.display_status || row.status) === "overdue").length,
  }), [items]);
  const canManagePayments = roleCanManagePayments(currentUser?.role || "");

  function openCreateModal() {
    setCreateError("");
    const defaultAccount = resolveDefaultPaymentAccount(paymentAccounts, "USD");
    setForm({
      ...initialForm,
      client_id: requestedClientId,
      case_id: requestedCaseId,
      payment_account_id: defaultAccount ? String(defaultAccount.id) : "",
      payment_instructions: defaultAccount?.payment_instructions || "",
    });
    setCreateOpen(true);
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setCreateError("");
    setTimeEntryError("");
    const defaultAccount = resolveDefaultPaymentAccount(paymentAccounts, "USD");
    setForm({
      ...initialForm,
      client_id: requestedClientId,
      case_id: requestedCaseId,
      payment_account_id: defaultAccount ? String(defaultAccount.id) : "",
      payment_instructions: defaultAccount?.payment_instructions || "",
    });
    if (searchParams.get("create") === "1") {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("create");
      const next = params.toString();
      router.replace(next ? `/dashboard/invoices?${next}` : "/dashboard/invoices");
    }
  }

  function addManualLineItem() {
    setForm((current) => ({
      ...current,
      line_items: [...current.line_items, makeManualLineItem()],
    }));
  }

  function addTimeEntryLine(entry) {
    setForm((current) => ({
      ...current,
      line_items: [...current.line_items, createTimeEntryLine(entry)],
    }));
  }

  function removeLineItem(index) {
    setForm((current) => ({
      ...current,
      line_items: current.line_items.length === 1 ? current.line_items : current.line_items.filter((_, rowIndex) => rowIndex !== index),
    }));
  }

  function updateLineItem(index, patch) {
    setForm((current) => {
      const next = [...current.line_items];
      next[index] = { ...next[index], ...patch };
      return { ...current, line_items: next };
    });
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

  async function handleCreate(event) {
    event.preventDefault();
    if (!form.client_id || !form.case_id || !form.issue_date) {
      setCreateError("Client, matter, and issue date are required.");
      return;
    }
    if (!form.payment_account_id) {
      setCreateError("A payment account is required for this invoice currency.");
      return;
    }

    const cleanLineItems = form.line_items
      .filter((row) => row.time_entry_id || row.description.trim())
      .map((row) => {
        if (row.time_entry_id) {
          return {
            line_type: row.line_type,
            description: row.description.trim() || "Time entry",
            time_entry_id: Number(row.time_entry_id),
          };
        }
        return {
          line_type: row.line_type,
          description: row.description.trim(),
          quantity: Number(row.quantity || 0),
          unit_price: Number(row.unit_price || 0),
          amount: row.amount !== "" ? Number(row.amount) : null,
        };
      });

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
          payment_account_id: Number(form.payment_account_id),
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
          <p className="vilo-state">No invoices found yet. Use Create Invoice to start the billing flow.</p>
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
                  <th>Payment Account</th>
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
                    <td>{row.payment_account?.account_name || "-"}</td>
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
          <div className="vilo-modal invoice-create-modal" onClick={(event) => event.stopPropagation()}>
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
                  <select value={form.client_id} onChange={(event) => setForm((current) => ({ ...current, client_id: event.target.value, case_id: "", line_items: [makeManualLineItem()] }))} required>
                    <option value="">Select client</option>
                    {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                </div>
                <div>
                  <label>Matter / Case *</label>
                  <select value={form.case_id} onChange={(event) => setForm((current) => ({ ...current, case_id: event.target.value, line_items: current.line_items.filter((item) => !item.time_entry_id).length ? current.line_items.filter((item) => !item.time_entry_id) : [makeManualLineItem()] }))} required>
                    <option value="">Select matter</option>
                    {caseOptions.map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
                  </select>
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Invoice Number</label>
                  <input value={form.invoice_number} onChange={(event) => setForm((current) => ({ ...current, invoice_number: event.target.value }))} placeholder="Auto-generate if blank" />
                </div>
                <div>
                  <label>Currency *</label>
                  <select value={form.currency} onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value }))} required>
                    <option value="USD">USD</option>
                    <option value="JMD">JMD</option>
                  </select>
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Payment Account *</label>
                  <select
                    value={form.payment_account_id}
                    onChange={(event) => {
                      const account = filteredPaymentAccounts.find((row) => Number(row.id) === Number(event.target.value));
                      setForm((current) => ({
                        ...current,
                        payment_account_id: event.target.value,
                        payment_instructions: account?.payment_instructions || current.payment_instructions,
                      }));
                    }}
                    required
                    disabled={!filteredPaymentAccounts.length}
                  >
                    <option value="">{paymentAccountWarning || "Select payment account"}</option>
                    {filteredPaymentAccounts.map((account) => <option key={account.id} value={account.id}>{account.account_name} · {account.bank_name}{account.is_default ? " · Default" : ""}</option>)}
                  </select>
                </div>
                <div>
                  <label>Issue Date *</label>
                  <input type="date" value={form.issue_date} onChange={(event) => setForm((current) => ({ ...current, issue_date: event.target.value }))} required />
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Due Date</label>
                  <input type="date" value={form.due_date} onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))} />
                </div>
                <div>
                  <label>GCT / Tax</label>
                  <input type="number" step="0.01" min="0" value={form.tax_amount} onChange={(event) => setForm((current) => ({ ...current, tax_amount: event.target.value }))} placeholder="0.00" />
                </div>
              </div>

              {paymentAccountWarning ? (
                <article className="settings-info-banner invoice-payment-warning">
                  <strong>No payment account configured for this currency.</strong>
                  <span>Add one in Settings before creating this invoice.</span>
                </article>
              ) : null}

              {selectedPaymentAccount ? (
                <article className="dashboard-card invoice-payment-account-preview">
                  <div className="dashboard-card__header">
                    <h2>Selected Payment Account</h2>
                  </div>
                  <div className="invoice-payment-account-preview__grid">
                    <span><strong>Bank:</strong> {selectedPaymentAccount.bank_name}</span>
                    <span><strong>Account:</strong> {selectedPaymentAccount.account_name}</span>
                    <span><strong>Number:</strong> {selectedPaymentAccount.account_number}</span>
                    {selectedPaymentAccount.swift_routing ? <span><strong>SWIFT / Routing:</strong> {selectedPaymentAccount.swift_routing}</span> : null}
                  </div>
                </article>
              ) : null}

              <div>
                <label>Payment Instructions</label>
                <input value={form.payment_instructions} onChange={(event) => setForm((current) => ({ ...current, payment_instructions: event.target.value }))} placeholder="Bank transfer, cheque, office payment..." />
              </div>

              <article className="dashboard-card invoice-time-entry-picker">
                <div className="invoice-line-items-editor__header">
                  <div>
                    <label>Add Billable Time Entries</label>
                    <p className="invoice-modal-copy">Imported time entries keep their staff, hours, rate, and line total. They remain separate from trust.</p>
                  </div>
                </div>
                {!form.case_id ? <p className="vilo-state">Select a matter to load billable time entries.</p> : null}
                {loadingTimeEntries ? <p className="vilo-state vilo-state--loading">Loading billable time entries...</p> : null}
                {timeEntryError ? <p className="vilo-state vilo-state--error">{timeEntryError}</p> : null}
                {!loadingTimeEntries && !timeEntryError && form.case_id && !availableBillableEntries.length ? <p className="vilo-state">No unbilled billable time entries available for this matter and currency.</p> : null}
                {!!availableBillableEntries.length ? (
                  <div className="vilo-table-wrap">
                    <table className="team-table">
                      <thead>
                        <tr>
                          <th>Staff</th>
                          <th>Description</th>
                          <th>Hours</th>
                          <th>Rate</th>
                          <th>Total</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {availableBillableEntries.map((entry) => (
                          <tr key={entry.id}>
                            <td>{entry.staff_name || "Staff"}</td>
                            <td>{entry.description || "-"}</td>
                            <td>{entry.duration_minutes ? (Number(entry.duration_minutes) / 60).toFixed(2) : "0.00"}</td>
                            <td>{formatMoney(entry.hourly_rate, entry.currency || form.currency)}</td>
                            <td>{formatMoney(entry.amount, entry.currency || form.currency)}</td>
                            <td><button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => addTimeEntryLine(entry)}>Add</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </article>

              <div className="invoice-line-items-editor">
                <div className="invoice-line-items-editor__header">
                  <div>
                    <label>Billable / Legal Line Items Only</label>
                    <p className="invoice-modal-copy">Trust deposits, retainers held in trust, escrow, and client funds are excluded by design.</p>
                  </div>
                  <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={addManualLineItem}>Add line item</button>
                </div>
                {form.line_items.map((item, index) => (
                  item.time_entry_id ? (
                    <div className="invoice-linked-time-row" key={`line-${index}`}>
                      <div className="invoice-linked-time-row__main">
                        <strong>{item.description}</strong>
                        <span>{item.staff_name} · {item.hours} hrs · {formatMoney(item.rate, form.currency)}</span>
                      </div>
                      <div className="invoice-linked-time-row__meta">
                        <span>{formatMoney(item.amount, form.currency)}</span>
                        <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => removeLineItem(index)}>Remove</button>
                      </div>
                    </div>
                  ) : (
                    <div className="invoice-line-item-row" key={`line-${index}`}>
                      <select value={item.line_type} onChange={(event) => updateLineItem(index, { line_type: event.target.value })}>
                        {LINE_ITEM_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                      <input value={item.description} onChange={(event) => updateLineItem(index, { description: event.target.value })} placeholder="Description" />
                      <input type="number" step="0.01" min="0.01" value={item.quantity} onChange={(event) => updateLineItem(index, { quantity: event.target.value })} placeholder="Qty" />
                      <input type="number" step="0.01" min="0" value={item.unit_price} onChange={(event) => updateLineItem(index, { unit_price: event.target.value })} placeholder="Unit price" />
                      <input type="number" step="0.01" min="0" value={item.amount} onChange={(event) => updateLineItem(index, { amount: event.target.value })} placeholder="Amount override" />
                      <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => removeLineItem(index)}>Remove</button>
                    </div>
                  )
                ))}
              </div>

              <div>
                <label>Notes</label>
                <textarea value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Optional invoice notes" />
              </div>

              {createError ? <p className="vilo-state vilo-state--error">{createError}</p> : null}

              <div className="vilo-table-actions invoice-create-actions">
                <button className="vilo-btn vilo-btn--secondary" type="button" onClick={closeCreateModal}>Cancel</button>
                <button className="vilo-btn vilo-btn--primary" type="submit" disabled={saving || !form.payment_account_id}>{saving ? "Creating..." : "Create Invoice"}</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
