"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

export default function PortalCasesPage() {
  const [rows, setRows] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    setError("");
    apiRequest(`/api/v1/portal/cases?page=${page}&page_size=10`)
      .then(setRows)
      .catch((err) => setError(err.message || "Failed to load cases"))
      .finally(() => setLoading(false));
  }, [page]);

  const hasPrev = rows.page > 1;
  const hasNext = rows.page * rows.page_size < rows.total;

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>My Cases</h1></div>
      {loading ? <p className="vilo-state">Loading cases...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
      {!loading && !error && !rows.items.length ? <p className="vilo-state">No cases found.</p> : null}
      {!loading && !error && rows.items.length ? (
        <article className="dashboard-card vilo-table-card">
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Title</th><th>Status</th><th>Priority</th><th>Action</th></tr></thead>
              <tbody>
                {rows.items.map((c) => (
                  <tr key={c.id}>
                    <td>{c.title}</td>
                    <td>{c.status}</td>
                    <td>{c.priority}</td>
                    <td><Link href={`/portal/cases/${c.id}`}>View</Link></td>
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
