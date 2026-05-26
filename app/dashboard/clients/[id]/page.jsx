"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest } from "../../../../lib/api";

export default function ClientDetailPage() {
  const { id } = useParams();
  const [client, setClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await apiRequest(`/api/v1/clients/${id}`);
        setClient(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  return (
    <section className="dashboard-page-stack">
      <div className="vilo-inline-actions">
        <Link href="/dashboard/clients" className="vilo-back-link">Back to clients</Link>
      </div>

      {loading ? <p className="vilo-state">Loading client...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      {client ? (
        <>
          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>{client.name}</h2></div>
            <div className="vilo-detail-grid">
              <p><strong>Email:</strong> {client.email || "-"}</p>
              <p><strong>Phone:</strong> {client.phone || "-"}</p>
              <p><strong>Address:</strong> {client.address || "-"}</p>
              <p><strong>Status:</strong> Active</p>
            </div>
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Notes</h2></div>
            <p className="vilo-card-copy">{client.notes || "No notes added for this client."}</p>
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Linked Cases</h2></div>
            <p className="vilo-card-copy">Case linking overview will appear here as more case analytics are added.</p>
          </article>
        </>
      ) : null}
    </section>
  );
}
