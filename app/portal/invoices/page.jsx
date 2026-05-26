"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

export default function PortalInvoicesPage() {
  const [rows, setRows] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    setError("");
    apiRequest(`/api/v1/portal/invoices?page=${page}&page_size=10`)
      .then(setRows)
      .catch((err) => setError(err.message || "Failed to load invoices"))
      .finally(() => setLoading(false));
  }, [page]);

  const hasPrev = rows.page > 1;
  const hasNext = rows.page * rows.page_size < rows.total;

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Invoices</h1></div>
      {loading ? <p className="vilo-state">Loading invoices...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
      {!loading && !error && !rows.items.length ? <p className="vilo-state">No invoices found.</p> : null}
      {!loading && !error && rows.items.length ? (
        <article className="dashboard-card vilo-table-card">
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Invoice</th><th>Status</th><th>Total</th><th>Balance Due</th><th>Action</th></tr></thead>
              <tbody>
                {rows.items.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoice_number}</td>
                    <td>{inv.status}</td>
                    <td>{money(inv.total)}</td>
                    <td>{money(inv.balance_due)}</td>
                    <td><Link href={`/portal/invoices/${inv.id}`}>View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="vilo-pagination">
            <button onClick={() => setPage((p) => p - 1)} disabled={!hasPrev}>Previous</button>
            <span>Page {rows.page}</span>
            <button onClick={() => setPage((p) => p + 1)} disabled={!hasNext}>Next</button>
          </div>
        </article>
      ) : null}
    </section>
  );
}
