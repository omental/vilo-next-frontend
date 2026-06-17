"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getCachedUser, setCachedUser } from "../../../../lib/auth";
import { apiDownload, apiRequest } from "../../../../lib/api";

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
      && invoice.status !== "paid"
      && invoice.status !== "cancelled",
  );

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
          {invoice.status === "draft" ? <button className="vilo-btn vilo-btn--secondary" type="button" onClick={markSent}>Mark Sent</button> : null}
          {canManage && invoice.balance_due > 0 ? (
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
            <strong><span className={`vilo-badge vilo-badge--${invoice.status}`}>{invoice.status}</span></strong>
            <span>Issue Date: {formatDate(invoice.issue_date)}</span>
            <span>Due Date: {formatDate(invoice.due_date)}</span>
            <span>Matter: {invoice.case_id ? `#${invoice.case_id}` : "Not linked"}</span>
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
        <strong>Available Trust Balance</strong>
        <span>{formatMoney(invoice.trust_balance_available || 0, currency)}</span>
        <p>Trust funds are transferred to Operating only when applied to an earned invoice. Trust deposits themselves are not invoice items or firm revenue.</p>
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

      {modal === "apply_trust" ? (
        <Modal title="Apply Trust Funds" copy="This creates a trust-to-operating transfer linked to the invoice payment record." onClose={closeModal}>
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
