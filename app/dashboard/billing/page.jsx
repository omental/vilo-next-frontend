"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getCachedUser, setCachedUser } from "../../../lib/auth";
import { apiRequest } from "../../../lib/api";

function roleCanView(role) {
  return role === "partner" || role === "admin" || role === "lawyer";
}

function formatMoney(value, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value || 0));
}

export default function BillingPage() {
  const [currentUser, setCurrentUser] = useState(getCachedUser());
  const [summary, setSummary] = useState([]);
  const [reports, setReports] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [response, invoiceReports] = await Promise.all([
          apiRequest("/api/v1/accounting/summary"),
          apiRequest("/api/v1/reports/invoices"),
        ]);
        setSummary(response.currencies || []);
        setReports(invoiceReports);
      } catch (err) {
        setError(err.message || "Failed to load accounting summary.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const totals = useMemo(() => {
    return summary.map((row) => ({
      ...row,
      trustNote: "Trust funds excluded from firm revenue",
    }));
  }, [summary]);

  if (currentUser && !roleCanView(currentUser.role)) {
    return (
      <section className="dashboard-page-stack">
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">You are not authorized to view accounting summaries.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="dashboard-page-stack billing-finance-page">
      <div className="dashboard-page-heading">
        <h1>Billing & Accounting</h1>
        <p className="invoice-page-intro">Firm operating revenue is shown here. Trust balances and trust deposits remain excluded until applied to an earned invoice.</p>
      </div>

      <div className="invoice-summary-grid billing-finance-links">
        <article className="dashboard-card invoice-summary-card invoice-summary-card--link">
          <span>Invoices</span>
          <strong>Review earned-fee invoices, direct payments, trust applications, and payment void history.</strong>
          <Link href="/dashboard/invoices">Go to Invoices</Link>
        </article>
        <article className="dashboard-card invoice-summary-card invoice-summary-card--link">
          <span>Trust Accounting</span>
          <strong>Monitor client funds, trust ledgers, receipts, disbursements, refunds, and audited adjustments.</strong>
          <Link href="/dashboard/trust">Go to Trust Accounting</Link>
        </article>
      </div>

      <article className="dashboard-card trust-compliance-banner">
        <strong>Operating funds only</strong>
        <span>Revenue, profit, and tax cards below exclude unapplied client trust funds and trust deposits by design.</span>
      </article>

      {error ? (
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">{error}</p>
        </div>
      ) : null}

      {loading ? (
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--loading">Loading accounting summary...</p>
        </div>
      ) : null}

      {!loading && !error && !totals.length ? (
        <div className="vilo-state-block">
          <p className="vilo-state">No accounting summary data available yet.</p>
        </div>
      ) : null}

      {!loading && !!totals.length ? (
        <div className="billing-currency-stack">
          {totals.map((row) => (
            <article key={row.currency} className="dashboard-card billing-currency-card">
              <div className="dashboard-card__header billing-currency-card__header">
                <div>
                  <h2>{row.currency} Operating Summary</h2>
                  <p>{row.trustNote}</p>
                </div>
                <span className="trust-summary-strip__chip">Trust excluded</span>
              </div>

              <div className="invoice-summary-grid billing-summary-grid">
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Revenue</span>
                  <strong>{formatMoney(row.revenue, row.currency)}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Direct Payment Total</span>
                  <strong>{formatMoney(row.direct_payment_total, row.currency)}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Trust Transfer Total</span>
                  <strong>{formatMoney(row.trust_transfer_total, row.currency)}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Expenses</span>
                  <strong>{formatMoney(row.expenses, row.currency)}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Profit</span>
                  <strong>{formatMoney(row.profit, row.currency)}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>GCT / Tax Payable</span>
                  <strong>{formatMoney(row.tax_payable, row.currency)}</strong>
                </article>
              </div>
            </article>
          ))}

          {reports ? (
            <article className="dashboard-card billing-currency-card">
              <div className="dashboard-card__header billing-currency-card__header">
                <div>
                  <h2>Invoice Reports</h2>
                  <p>Revenue is based on non-voided invoice payments only. Trust deposits remain excluded.</p>
                </div>
              </div>
              <div className="invoice-summary-grid billing-summary-grid">
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Paid Invoices</span>
                  <strong>{reports.totals?.paid_count || 0}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Unpaid Invoices</span>
                  <strong>{reports.totals?.unpaid_count || 0}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Overdue Invoices</span>
                  <strong>{reports.totals?.overdue_count || 0}</strong>
                </article>
                <article className="invoice-summary-card invoice-summary-card--financial">
                  <span>Outstanding Balance</span>
                  <strong>{formatMoney(reports.totals?.outstanding_balance || 0, "USD")}</strong>
                </article>
              </div>
              <div className="vilo-table-wrap">
                <table className="team-table">
                  <thead><tr><th>Payment Method</th><th>Invoice Count</th><th>Paid Total</th></tr></thead>
                  <tbody>
                    {Object.entries(reports.payment_method_report?.counts || {}).map(([label, count]) => (
                      <tr key={label}>
                        <td>{label}</td>
                        <td>{count}</td>
                        <td>{formatMoney(reports.payment_method_report?.totals?.[label] || 0, "USD")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
