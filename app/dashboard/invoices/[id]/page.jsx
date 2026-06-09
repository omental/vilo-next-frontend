"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiDownload, apiRequest } from "../../../../lib/api";

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function renderFirmLines(organization) {
  const lines = [organization?.name || "Firm"];
  if (organization?.address) lines.push(organization.address);
  if (organization?.email) lines.push(organization.email);
  if (organization?.phone) lines.push(organization.phone);
  if (organization?.tax_number) lines.push(`Tax/VAT: ${organization.tax_number}`);
  return lines;
}

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const [inv, setInv] = useState(null);
  const [sum, setSum] = useState(null);
  const [trusts, setTrusts] = useState([]);
  const [error, setError] = useState("");
  const [applyForm, setApplyForm] = useState({ trust_account_id: "", amount: "", description: "" });

  async function load() {
    setError("");
    try {
      const [a, b, c] = await Promise.all([
        apiRequest(`/api/v1/invoices/${id}`),
        apiRequest(`/api/v1/invoices/${id}/summary`),
        apiRequest("/api/v1/trust/accounts").catch(() => []),
      ]);
      setInv(a);
      setSum(b);
      setTrusts(c);
    } catch (err) {
      setError(err.message || "Failed to load invoice");
    }
  }

  useEffect(() => {
    if (!id) return;
    load();
  }, [id]);

  async function markSent() {
    setError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-sent`, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to mark invoice as sent");
    }
  }

  async function markPaid() {
    setError("");
    try {
      await apiRequest(`/api/v1/invoices/${id}/mark-paid`, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err.message || "Failed to mark invoice as paid");
    }
  }

  async function applyTrust(e) {
    e.preventDefault();
    await apiRequest("/api/v1/trust/apply-to-invoice", {
      method: "POST",
      body: JSON.stringify({
        trust_account_id: Number(applyForm.trust_account_id),
        client_id: Number(inv.client_id),
        case_id: inv.case_id ?? null,
        invoice_id: Number(id),
        amount: Number(applyForm.amount),
        description: applyForm.description || null,
      }),
    });
    setApplyForm({ ...applyForm, amount: "", description: "" });
    await load();
  }

  if (error && !inv) return <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div>;
  if (!inv) return <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading invoice...</p></div>;

  const firmLines = renderFirmLines(inv.organization);

  return (
    <section className="dashboard-page-stack">
      <div className="invoice-detail-top-row">
        <div>
          <h1>Invoice {inv.invoice_number}</h1>
          <p><Link href="/dashboard/invoices">Invoices</Link> &gt; Invoice Detail</p>
        </div>
        <div className="invoice-page-actions">
          <button className="vilo-btn vilo-btn--ghost" type="button" onClick={() => apiDownload(`/api/v1/invoices/${id}/pdf`)}>Download PDF</button>
          {inv.status === "draft" ? <button className="vilo-btn vilo-btn--secondary" type="button" onClick={markSent}>Mark sent</button> : null}
          {inv.status !== "paid" ? <button className="vilo-btn vilo-btn--primary" type="button" onClick={markPaid}>Mark paid</button> : null}
        </div>
      </div>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      <article className="dashboard-card invoice-hero-card">
        <div className="invoice-hero-grid">
          <div className="invoice-party-card">
            <span className="invoice-party-label">Firm Details</span>
            {firmLines.map((line) => <strong key={line}>{line}</strong>)}
          </div>
          <div className="invoice-party-card">
            <span className="invoice-party-label">Bill To</span>
            <strong>{inv.client?.name || `Client #${inv.client_id}`}</strong>
            {inv.client?.address ? <span>{inv.client.address}</span> : null}
            {inv.client?.email ? <span>{inv.client.email}</span> : null}
            {inv.client?.phone ? <span>{inv.client.phone}</span> : null}
            {inv.client?.occupation ? <span>Occupation: {inv.client.occupation}</span> : null}
          </div>
          <div className="invoice-party-card">
            <span className="invoice-party-label">Invoice Summary</span>
            <strong><span className={`vilo-badge vilo-badge--${inv.status}`}>{inv.status}</span></strong>
            <span>Issue Date: {formatDate(inv.issue_date)}</span>
            <span>Due Date: {formatDate(inv.due_date)}</span>
            <span>Case: {inv.case_id ? `#${inv.case_id}` : "-"}</span>
          </div>
        </div>
      </article>

      <article className="dashboard-card vilo-detail-card">
        <div className="dashboard-card__header"><h2>Totals</h2></div>
        <div className="vilo-detail-grid">
          <p><strong>Subtotal:</strong> {money(inv.subtotal)}</p>
          <p><strong>Tax:</strong> {money(inv.tax_amount)}</p>
          <p><strong>Total:</strong> {money(inv.total)}</p>
          <p><strong>Paid:</strong> {money(inv.paid_amount)}</p>
          <p><strong>Balance Due:</strong> {money(inv.balance_due)}</p>
          <p><strong>Line Items:</strong> {sum ? sum.line_items_count : inv.line_items.length}</p>
        </div>
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Line Items</h2></div>
        {inv.line_items.length ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Type</th><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead>
              <tbody>
                {inv.line_items.map((li) => (
                  <tr key={li.id}>
                    <td>{li.line_type}</td>
                    <td>{li.description}</td>
                    <td>{li.quantity}</td>
                    <td>{money(li.unit_price)}</td>
                    <td>{money(li.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="vilo-state-block"><p className="vilo-state">This invoice has no line items yet.</p></div>}
      </article>

      {inv.notes ? (
        <article className="dashboard-card vilo-detail-card">
          <div className="dashboard-card__header"><h2>Notes</h2></div>
          <p className="vilo-card-copy">{inv.notes}</p>
        </article>
      ) : null}

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Apply Trust Funds</h2></div>
        <form className="vilo-form-grid" onSubmit={applyTrust}>
          <select value={applyForm.trust_account_id} onChange={(e) => setApplyForm({ ...applyForm, trust_account_id: e.target.value })} required>
            <option value="">Trust Account</option>
            {trusts.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <input type="number" step="0.01" placeholder="Amount" value={applyForm.amount} onChange={(e) => setApplyForm({ ...applyForm, amount: e.target.value })} required />
          <input placeholder="Description" value={applyForm.description} onChange={(e) => setApplyForm({ ...applyForm, description: e.target.value })} />
          <button className="vilo-btn vilo-btn--primary" type="submit">Apply Trust</button>
        </form>
      </article>
    </section>
  );
}
