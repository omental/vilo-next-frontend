"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getCachedUser, setCachedUser } from "../../../../lib/auth";
import { apiDownload, apiRequest } from "../../../../lib/api";

const LINE_ITEM_TYPE_OPTIONS = [
  ["legal_fee", "Legal Fee"],
  ["hourly_work", "Hourly Work"],
  ["flat_fee", "Flat Fee"],
  ["disbursement", "Disbursement"],
  ["expense", "Expense"],
  ["approved_billable_expense", "Approved Billable Expense"],
];

function roleCanManage(role) {
  return role === "partner" || role === "admin";
}

function formatMoney(value, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function invoiceCurrency(invoice) {
  return invoice?.payments?.[0]?.currency || invoice?.currency || "USD";
}

function renderFirmLines(organization) {
  const lines = [organization?.name || "Firm"];
  if (organization?.address) lines.push(organization.address);
  if (organization?.email) lines.push(organization.email);
  if (organization?.phone) lines.push(organization.phone);
  if (organization?.tax_number) lines.push(`Tax / TRN: ${organization.tax_number}`);
  return lines;
}

function EmptyState({ message, error = false }) {
  return (
    <div className="vilo-state-block">
      <p className={error ? "vilo-state vilo-state--error" : "vilo-state"}>{message}</p>
    </div>
  );
}

function Modal({ title, copy, onClose, children }) {
  return (
    <div className="vilo-modal-overlay" onClick={onClose}>
      <div className="vilo-modal invoice-finance-modal" onClick={(event) => event.stopPropagation()}>
        <div className="vilo-modal__header">
          <div>
            <h3>{title}</h3>
            {copy ? <p className="invoice-modal-copy">{copy}</p> : null}
          </div>
          <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={onClose}>Close</button>
        </div>
        <div className="vilo-modal__body">{children}</div>
      </div>
    </div>
  );
}

function InvoiceDetailInner() {
  const { id } = useParams();
  const searchParams = useSearchParams();
  const [currentUser, setCurrentUser] = useState(getCachedUser());
  const [invoice, setInvoice] = useState(null);
  const [trustAccounts, setTrustAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [modal, setModal] = useState("");
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [applyForm, setApplyForm] = useState({
    amount: "",
    trust_account_id: "",
    payment_date: "",
    reference_number: "",
    description: "",
  });
  const [voidReason, setVoidReason] = useState("");

  const requestedApplyTrust = searchParams.get("apply_trust") === "1";

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

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [invoiceRow, trustRows] = await Promise.all([
        apiRequest(`/api/v1/invoices/${id}`),
        apiRequest("/api/v1/trust/accounts").catch(() => []),
      ]);
      setInvoice(invoiceRow);
      setTrustAccounts(trustRows || []);
    } catch (err) {
      setError(err.message || "Failed to load invoice.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!id) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const canManage = roleCanManage(currentUser?.role || "");
  const firmLines = useMemo(() => renderFirmLines(invoice?.organization), [invoice?.organization]);
  const activePayments = useMemo(() => (invoice?.payments || []).filter((row) => !row.voided_at), [invoice?.payments]);
  const currency = invoiceCurrency(invoice);
  const eligibleTrustAccounts = useMemo(
    () => trustAccounts.filter((row) => (row.currency || "USD").toUpperCase() === currency.toUpperCase()),
    [currency, trustAccounts],
  );
  const canApplyTrust = Boolean(
    canManage
      && invoice
      && invoice.balance_due > 0
      && Number(invoice.trust_balance_available || 0) > 0
      && !["paid", "cancelled"].includes(invoice.display_status || invoice.status),
  );

  useEffect(() => {
    if (!invoice) return;
    setEditForm({
      client_id: String(invoice.client_id || ""),
      case_id: String(invoice.case_id || ""),
      invoice_number: invoice.invoice_number || "",
      currency: invoice.currency || currency,
      issue_date: invoice.issue_date || "",
      due_date: invoice.due_date || "",
      tax_amount: String(invoice.tax_amount || ""),
      notes: invoice.notes || "",
      payment_instructions: invoice.payment_instructions || "",
      line_items: (invoice.line_items || []).map((line) => ({
        line_type: line.line_type,
        description: line.description,
        quantity: String(line.quantity),
        unit_price: String(line.unit_price),
        amount: String(line.amount),
      })),
    });
  }, [currency, invoice]);

  useEffect(() => {
    if (!invoice) return;
    const defaultAccount = eligibleTrustAccounts[0]?.id ? String(eligibleTrustAccounts[0].id) : "";
    setApplyForm((current) => ({
      ...current,
      trust_account_id: current.trust_account_id || defaultAccount,
      payment_date: current.payment_date || new Date().toISOString().slice(0, 10),
      description: current.description || `Applied trust funds to Invoice ${invoice.invoice_number}`,
    }));
  }, [eligibleTrustAccounts, invoice]);

  useEffect(() => {
    if (requestedApplyTrust && invoice && canApplyTrust) {
      setFormError("");
      setModal("apply_trust");
    }
  }, [requestedApplyTrust, invoice, canApplyTrust]);

  function closeModal() {
    setModal("");
    setSelectedPayment(null);
    setVoidReason("");
    setFormError("");
  }

  async function markSent() {
    setError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-sent`, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to mark invoice as sent.");
    }
  }

  async function submitDirectPayment(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-paid`, { method: "PATCH" });
      closeModal();
      await load();
    } catch (err) {
      setFormError(err.message || "Failed to record direct payment.");
    } finally {
      setSaving(false);
    }
  }

  async function submitApplyTrust(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/apply-trust`, {
        method: "POST",
        body: JSON.stringify({
          amount: Number(applyForm.amount),
          trust_account_id: applyForm.trust_account_id ? Number(applyForm.trust_account_id) : null,
          payment_date: applyForm.payment_date || null,
          reference_number: applyForm.reference_number || null,
          description: applyForm.description || null,
        }),
      });
      closeModal();
      setApplyForm((current) => ({ ...current, amount: "", reference_number: "" }));
      await load();
    } catch (err) {
      setFormError(err.message || "Failed to apply trust funds.");
    } finally {
      setSaving(false);
    }
  }

  async function submitVoidPayment(event) {
    event.preventDefault();
    if (!selectedPayment) return;
    setSaving(true);
    setFormError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/payments/${selectedPayment.id}/void`, {
        method: "POST",
        body: JSON.stringify({ void_reason: voidReason }),
      });
      closeModal();
      await load();
    } catch (err) {
      setFormError(err.message || "Failed to void invoice payment.");
    } finally {
      setSaving(false);
    }
  }

  async function submitEditInvoice(event) {
    event.preventDefault();
    if (!editForm?.case_id) {
      setFormError("Matter is required.");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          client_id: Number(editForm.client_id),
          case_id: Number(editForm.case_id),
          invoice_number: editForm.invoice_number || null,
          currency: editForm.currency,
          issue_date: editForm.issue_date,
          due_date: editForm.due_date || null,
          tax_amount: Number(editForm.tax_amount || 0),
          notes: editForm.notes || null,
          payment_instructions: editForm.payment_instructions || null,
          line_items: (editForm.line_items || []).filter((line) => line.description.trim()).map((line) => ({
            line_type: line.line_type,
            description: line.description.trim(),
            quantity: Number(line.quantity || 0),
            unit_price: Number(line.unit_price || 0),
            amount: Number(line.amount || 0),
          })),
        }),
      });
      closeModal();
      await load();
    } catch (err) {
      setFormError(err.message || "Failed to update invoice.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !invoice) return <EmptyState message={error} error />;
  if (loading && !invoice) return <EmptyState message="Loading invoice..." />;
  if (!invoice) return <EmptyState message="Invoice not found." error />;

  return (
    <section className="dashboard-page-stack invoice-finance-page">
      <div className="invoice-detail-top-row">
        <div>
          <h1>Invoice {invoice.invoice_number}</h1>
          <p><Link href="/dashboard/invoices">Invoices</Link> &gt; Invoice Detail</p>
        </div>
        <div className="invoice-page-actions">
          <button className="vilo-btn vilo-btn--ghost" type="button" onClick={() => apiDownload(`/api/v1/invoices/${id}/pdf`)}>Download PDF</button>
          {invoice.status === "draft" ? <button className="vilo-btn vilo-btn--secondary" type="button" onClick={markSent}>Send Invoice</button> : null}
          {canManage ? (
            <button className="vilo-btn vilo-btn--secondary" type="button" onClick={() => { setFormError(""); setModal("edit_invoice"); }}>
              Edit Invoice
            </button>
          ) : null}
          {canManage && invoice.balance_due > 0 && !["paid", "cancelled"].includes(invoice.display_status || invoice.status) ? (
            <button className="vilo-btn vilo-btn--secondary" type="button" onClick={() => { setFormError(""); setModal("direct_payment"); }}>
              Record Direct Payment
            </button>
          ) : null}
          {canApplyTrust ? (
            <button className="vilo-btn vilo-btn--primary" type="button" onClick={() => { setFormError(""); setModal("apply_trust"); }}>
              Apply Trust Funds
            </button>
          ) : null}
        </div>
      </div>

      {error ? <EmptyState message={error} error /> : null}

      <article className="dashboard-card invoice-hero-card">
        <div className="invoice-hero-grid">
          <div className="invoice-party-card">
            <span className="invoice-party-label">Firm Details</span>
            {firmLines.map((line) => <strong key={line}>{line}</strong>)}
          </div>
          <div className="invoice-party-card">
            <span className="invoice-party-label">Bill To</span>
            <strong>{invoice.client?.name || `Client #${invoice.client_id}`}</strong>
            {invoice.client?.address ? <span>{invoice.client.address}</span> : null}
            {invoice.client?.email ? <span>{invoice.client.email}</span> : null}
            {invoice.client?.phone ? <span>{invoice.client.phone}</span> : null}
          </div>
          <div className="invoice-party-card">
            <span className="invoice-party-label">Invoice Status</span>
            <strong><span className={`vilo-badge vilo-badge--${invoice.display_status || invoice.status}`}>{invoice.display_status || invoice.status}</span></strong>
            <span>Issue Date: {formatDate(invoice.issue_date)}</span>
            <span>Due Date: {formatDate(invoice.due_date)}</span>
            <span>Matter: {invoice.matter_title || (invoice.case_id ? `#${invoice.case_id}` : "Not linked")}</span>
            <span>Payment Method: {invoice.payment_method_summary}</span>
          </div>
        </div>
      </article>

      <div className="invoice-summary-grid">
        <article className="dashboard-card invoice-summary-card">
          <span>Subtotal</span>
          <strong>{formatMoney(invoice.subtotal, currency)}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>GCT / Tax</span>
          <strong>{formatMoney(invoice.tax_amount, currency)}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Paid Amount</span>
          <strong>{formatMoney(invoice.paid_amount, currency)}</strong>
        </article>
        <article className="dashboard-card invoice-summary-card">
          <span>Balance Due</span>
          <strong>{formatMoney(invoice.balance_due, currency)}</strong>
        </article>
      </div>

      <article className="dashboard-card invoice-trust-banner">
        <strong>Client Trust Balance (Matter): {formatMoney(invoice.trust_balance_available || 0, currency)}</strong>
        <span>This balance is informational only and does not affect this invoice until Apply Trust Funds is used.</span>
        <p>Only funds held for this same client and matter can be applied. Trust deposits themselves are not invoice items or firm revenue.</p>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Line Items</h2></div>
        {invoice.line_items.length ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Qty</th>
                  <th>Unit</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.line_items.map((line) => (
                  <tr key={line.id}>
                    <td>{line.line_type}</td>
                    <td>{line.description}</td>
                    <td>{line.quantity}</td>
                    <td>{formatMoney(line.unit_price, currency)}</td>
                    <td>{formatMoney(line.amount, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState message="This invoice has no line items yet." />}
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header">
          <h2>Payment History</h2>
        </div>
        {!invoice.payments?.length ? <EmptyState message="This invoice has no payments yet." /> : (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Source</th>
                  <th>Amount</th>
                  <th>Reference</th>
                  <th>Status</th>
                  <th>Links</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((payment) => (
                  <tr key={payment.id} className={payment.voided_at ? "invoice-payment-row invoice-payment-row--voided" : "invoice-payment-row"}>
                    <td>{formatDate(payment.paid_at)}</td>
                    <td>{payment.payment_source === "trust" ? "Trust Transfer" : "Direct Payment"}</td>
                    <td>{formatMoney(payment.amount, payment.currency || currency)}</td>
                    <td>{payment.reference_number || "-"}</td>
                    <td>
                      <span className={`vilo-badge trust-status-badge trust-status-badge--${payment.voided_at ? "voided" : "active"}`}>
                        {payment.voided_at ? "voided" : "active"}
                      </span>
                      {payment.void_reason ? <div className="invoice-payment-note">Reason: {payment.void_reason}</div> : null}
                    </td>
                    <td className="invoice-payment-links">
                      {payment.linked_trust_transaction_id ? <span>Trust #{payment.linked_trust_transaction_id}</span> : null}
                      {payment.linked_operating_transaction_id ? <span>Operating #{payment.linked_operating_transaction_id}</span> : null}
                    </td>
                    <td>
                      {canManage && !payment.voided_at ? (
                        <button
                          type="button"
                          className="vilo-btn vilo-btn--secondary vilo-btn--xs"
                          onClick={() => {
                            setSelectedPayment(payment);
                            setVoidReason("");
                            setFormError("");
                            setModal("void_payment");
                          }}
                        >
                          Void
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </article>

      {invoice.notes ? (
        <article className="dashboard-card vilo-detail-card">
          <div className="dashboard-card__header"><h2>Notes</h2></div>
          <p className="vilo-card-copy">{invoice.notes}</p>
        </article>
      ) : null}

      {invoice.payment_instructions ? (
        <article className="dashboard-card vilo-detail-card">
          <div className="dashboard-card__header"><h2>Payment Instructions</h2></div>
          <p className="vilo-card-copy">{invoice.payment_instructions}</p>
        </article>
      ) : null}

      {modal === "edit_invoice" && editForm ? (
        <Modal title="Edit Invoice" copy="Billable/legal line items only. Trust deposits and client funds remain outside the invoice." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitEditInvoice}>
            <div className="vilo-form-row-two">
              <input value={editForm.invoice_number} onChange={(event) => setEditForm((current) => ({ ...current, invoice_number: event.target.value }))} placeholder="Invoice number" />
              <select value={editForm.currency} onChange={(event) => setEditForm((current) => ({ ...current, currency: event.target.value }))}>
                <option value="USD">USD</option>
                <option value="JMD">JMD</option>
              </select>
            </div>
            <div className="vilo-form-row-two">
              <input type="date" value={editForm.issue_date} onChange={(event) => setEditForm((current) => ({ ...current, issue_date: event.target.value }))} required />
              <input type="date" value={editForm.due_date} onChange={(event) => setEditForm((current) => ({ ...current, due_date: event.target.value }))} />
            </div>
            <div className="vilo-form-row-two">
              <input value={editForm.case_id} onChange={(event) => setEditForm((current) => ({ ...current, case_id: event.target.value }))} placeholder="Matter ID" required />
              <input type="number" step="0.01" min="0" value={editForm.tax_amount} onChange={(event) => setEditForm((current) => ({ ...current, tax_amount: event.target.value }))} placeholder="GCT / Tax" />
            </div>
            <input value={editForm.payment_instructions} onChange={(event) => setEditForm((current) => ({ ...current, payment_instructions: event.target.value }))} placeholder="Payment instructions" />
            {(editForm.line_items || []).map((line, index) => (
              <div className="invoice-line-item-row" key={`edit-line-${index}`}>
                <select value={line.line_type} onChange={(event) => setEditForm((current) => {
                  const next = [...current.line_items];
                  next[index] = { ...next[index], line_type: event.target.value };
                  return { ...current, line_items: next };
                })}>
                  {LINE_ITEM_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <input value={line.description} onChange={(event) => setEditForm((current) => {
                  const next = [...current.line_items];
                  next[index] = { ...next[index], description: event.target.value };
                  return { ...current, line_items: next };
                })} placeholder="Description" />
                <input type="number" step="0.01" min="0.01" value={line.quantity} onChange={(event) => setEditForm((current) => {
                  const next = [...current.line_items];
                  next[index] = { ...next[index], quantity: event.target.value };
                  return { ...current, line_items: next };
                })} placeholder="Qty" />
                <input type="number" step="0.01" min="0" value={line.unit_price} onChange={(event) => setEditForm((current) => {
                  const next = [...current.line_items];
                  next[index] = { ...next[index], unit_price: event.target.value };
                  return { ...current, line_items: next };
                })} placeholder="Unit price" />
                <input type="number" step="0.01" min="0" value={line.amount} onChange={(event) => setEditForm((current) => {
                  const next = [...current.line_items];
                  next[index] = { ...next[index], amount: event.target.value };
                  return { ...current, line_items: next };
                })} placeholder="Amount" />
              </div>
            ))}
            <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => setEditForm((current) => ({
              ...current,
              line_items: [...current.line_items, { line_type: "legal_fee", description: "", quantity: "1", unit_price: "", amount: "" }],
            }))}>
              Add line item
            </button>
            <textarea placeholder="Notes" value={editForm.notes} onChange={(event) => setEditForm((current) => ({ ...current, notes: event.target.value }))} />
            <div className="vilo-table-actions invoice-create-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Save invoice"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "apply_trust" ? (
        <Modal title="Apply Trust Funds" copy="Only funds held for this same client and matter can be applied." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitApplyTrust}>
            <div className="invoice-action-review">
              <span>Invoice balance due</span>
              <strong>{formatMoney(invoice.balance_due, currency)}</strong>
              <span>Available trust balance</span>
              <strong>{formatMoney(invoice.trust_balance_available || 0, currency)}</strong>
            </div>
            <div className="vilo-form-row-two">
              <input type="number" step="0.01" min="0" max={Math.min(Number(invoice.balance_due || 0), Number(invoice.trust_balance_available || 0))} placeholder="Amount" value={applyForm.amount} onChange={(event) => setApplyForm((current) => ({ ...current, amount: event.target.value }))} required />
              <select value={applyForm.trust_account_id} onChange={(event) => setApplyForm((current) => ({ ...current, trust_account_id: event.target.value }))}>
                <option value="">Default trust account</option>
                {eligibleTrustAccounts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <input type="date" value={applyForm.payment_date} onChange={(event) => setApplyForm((current) => ({ ...current, payment_date: event.target.value }))} />
              <input placeholder="Reference number" value={applyForm.reference_number} onChange={(event) => setApplyForm((current) => ({ ...current, reference_number: event.target.value }))} />
            </div>
            <textarea placeholder="Description" value={applyForm.description} onChange={(event) => setApplyForm((current) => ({ ...current, description: event.target.value }))} />
            <div className="vilo-table-actions invoice-create-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Applying..." : "Apply trust funds"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "direct_payment" ? (
        <Modal title="Record Direct Payment" copy="This records a direct operating payment for the remaining invoice balance. It does not touch trust balances." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitDirectPayment}>
            <div className="invoice-action-review">
              <span>Remaining balance</span>
              <strong>{formatMoney(invoice.balance_due, currency)}</strong>
              <span>Active payments on invoice</span>
              <strong>{activePayments.length}</strong>
            </div>
            <p className="trust-form-warning">The current backend records direct payment for the remaining balance only.</p>
            <div className="vilo-table-actions invoice-create-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Recording..." : "Record direct payment"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "void_payment" && selectedPayment ? (
        <Modal
          title="Void Invoice Payment"
          copy={selectedPayment.payment_source === "trust"
            ? "This will reverse the trust-to-operating transfer and restore funds to trust."
            : "This will reverse the recorded operating payment."}
          onClose={closeModal}
        >
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitVoidPayment}>
            <div className="invoice-action-review">
              <span>Payment source</span>
              <strong>{selectedPayment.payment_source === "trust" ? "Trust Transfer" : "Direct Payment"}</strong>
              <span>Amount</span>
              <strong>{formatMoney(selectedPayment.amount, selectedPayment.currency || currency)}</strong>
            </div>
            <textarea placeholder="Void reason" value={voidReason} onChange={(event) => setVoidReason(event.target.value)} required />
            <div className="vilo-table-actions invoice-create-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Voiding..." : "Void payment"}</button>
            </div>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}

export default function InvoiceDetailPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><EmptyState message="Loading invoice..." /></section>}>
      <InvoiceDetailInner />
    </Suspense>
  );
}
