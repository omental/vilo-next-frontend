"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiDownload, apiRequest } from "../../../../lib/api";

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

export default function PortalInvoiceDetailPage() {
  const params = useParams();
  const id = params?.id;
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    apiRequest(`/api/v1/portal/invoices/${id}`)
      .then(setInvoice)
      .catch((err) => setError(err.message || "Failed to load invoice"))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Invoice Detail</h1></div>
      <Link href="/portal/invoices">Back to invoices</Link>
      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading invoice...</p></div> : null}
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {!loading && !error && invoice ? (
        <>
          <article className="dashboard-card vilo-table-card">
            <div className="vilo-form-grid">
              <button className="vilo-btn vilo-btn--primary" type="button" onClick={() => apiDownload(`/api/v1/invoices/${id}/pdf`)}>Download PDF</button>
            </div>
          </article>
          <article className="dashboard-card vilo-table-card">
            <div className="dashboard-card__header"><h2>{invoice.invoice_number}</h2></div>
            <p className="vilo-state">Status: <span className={`vilo-badge vilo-badge--${invoice.status}`}>{invoice.status}</span></p>
            <p className="vilo-state">Total: {money(invoice.total)} | Paid: {money(invoice.paid_amount)} | Balance Due: {money(invoice.balance_due)}</p>
          </article>
          <article className="dashboard-card vilo-table-card">
            <div className="dashboard-card__header"><h2>Line Items</h2></div>
            {!invoice.line_items?.length ? <p className="vilo-state">No line items.</p> : (
              <div className="vilo-table-wrap">
                <table className="team-table">
                  <thead><tr><th>Description</th><th>Type</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead>
                  <tbody>
                    {invoice.line_items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.description}</td>
                        <td>{item.line_type}</td>
                        <td>{item.quantity}</td>
                        <td>{money(item.unit_price)}</td>
                        <td>{money(item.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
}
