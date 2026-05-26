"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../../lib/api";

function fmtCurrency(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n);
}

function fmtDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const res = await apiRequest("/api/v1/reports/dashboard-summary");
        if (mounted) setData(res);
      } catch (err) {
        if (mounted) setError(err.message || "Failed to load dashboard summary");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const cards = useMemo(() => {
    if (!data) return [];
    return [
      { label: "Total Clients", value: data.total_clients ?? 0 },
      { label: "Active Cases", value: data.active_cases ?? 0 },
      { label: "Pending Tasks", value: data.pending_tasks ?? 0 },
      { label: "Outstanding Invoices", value: data.outstanding_invoices ?? 0 },
      { label: "Trust Balance", value: fmtCurrency(data.total_trust_balance) },
      { label: "Balance Due", value: fmtCurrency(data.total_balance_due) },
    ];
  }, [data]);

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Dashboard</h1></div>

      {loading ? <p className="vilo-state">Loading dashboard metrics...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      {!loading && !error && data ? (
        <>
          <div className="dashboard-row-grid">
            {cards.map((card) => (
              <article key={card.label} className="dashboard-card vilo-table-card">
                <div className="dashboard-card__header"><h2>{card.label}</h2></div>
                <div style={{ padding: "0 1.25rem 1.25rem", fontSize: "1.75rem", fontWeight: 700 }}>{card.value}</div>
              </article>
            ))}
          </div>

          <div className="dashboard-row-grid" style={{ marginTop: "1rem" }}>
            <article className="dashboard-card vilo-table-card">
              <div className="dashboard-card__header"><h2>Recent Activity</h2></div>
              {data.recent_activity?.length ? (
                <div className="vilo-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Event</th><th>Case</th><th>When</th></tr></thead>
                    <tbody>
                      {data.recent_activity.slice(0, 10).map((item) => (
                        <tr key={item.id}>
                          <td>{item.title || item.event_type}</td>
                          <td>{item.case_id ? `#${item.case_id}` : "-"}</td>
                          <td>{fmtDate(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="vilo-state">No recent activity.</p>}
            </article>

            <article className="dashboard-card vilo-table-card">
              <div className="dashboard-card__header"><h2>Upcoming Events</h2></div>
              {data.upcoming_events_items?.length ? (
                <div className="vilo-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Title</th><th>Type</th><th>Start</th></tr></thead>
                    <tbody>
                      {data.upcoming_events_items.map((item) => (
                        <tr key={item.id}>
                          <td>{item.title}</td>
                          <td>{item.event_type}</td>
                          <td>{fmtDate(item.start_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="vilo-state">No upcoming events.</p>}
            </article>
          </div>

          <div className="dashboard-row-grid" style={{ marginTop: "1rem" }}>
            <article className="dashboard-card vilo-table-card">
              <div className="dashboard-card__header"><h2>Overdue Tasks</h2></div>
              {data.overdue_tasks_items?.length ? (
                <div className="vilo-table-wrap">
                  <table className="team-table">
                    <thead><tr><th>Title</th><th>Status</th><th>Due</th></tr></thead>
                    <tbody>
                      {data.overdue_tasks_items.map((task) => (
                        <tr key={task.id}>
                          <td>{task.title}</td>
                          <td>{task.status}</td>
                          <td>{fmtDate(task.due_date)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="vilo-state">No overdue tasks.</p>}
            </article>

            <article className="dashboard-card vilo-table-card">
              <div className="dashboard-card__header"><h2>Financial Snapshot</h2></div>
              <div style={{ padding: "0 1.25rem 1.25rem" }}>
                <p><strong>Invoice Total:</strong> {fmtCurrency(data.total_invoice_amount)}</p>
                <p><strong>Paid Total:</strong> {fmtCurrency(data.total_paid_amount)}</p>
                <p><strong>Balance Due:</strong> {fmtCurrency(data.total_balance_due)}</p>
                <p><strong>Trust Balance:</strong> {fmtCurrency(data.total_trust_balance)}</p>
              </div>
            </article>
          </div>
        </>
      ) : null}
    </section>
  );
}
