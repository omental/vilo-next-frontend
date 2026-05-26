"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

export default function InvoicesPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(){
    setLoading(true);
    setError("");
    try {
      setItems(await apiRequest('/api/v1/invoices'));
    } catch (err) {
      setError(err.message || "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  }
  useEffect(()=>{load();},[]);

  async function sent(id){ await apiRequest(`/api/v1/invoices/${id}/mark-sent`,{method:'PATCH'}); await load(); }
  async function paid(id){ await apiRequest(`/api/v1/invoices/${id}/mark-paid`,{method:'PATCH'}); await load(); }

  return <section className="dashboard-page-stack"><div className="dashboard-page-heading"><h1>Invoices</h1></div>
    {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading invoices...</p></div> : null}
    {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
    {!loading && !error && !items.length ? <div className="vilo-state-block"><p className="vilo-state">No invoices found yet.</p></div> : null}
    {!loading && !error && items.length ? <article className="dashboard-card vilo-table-card"><div className="dashboard-card__header"><h2>Invoice List</h2></div><div className="vilo-table-wrap"><table className="team-table"><thead><tr><th>No</th><th>Status</th><th>Client</th><th>Case</th><th>Total</th><th>Actions</th></tr></thead><tbody>{items.map((x)=><tr key={x.id}><td>{x.invoice_number}</td><td><span className={`vilo-badge vilo-badge--${x.status}`}>{x.status}</span></td><td>#{x.client_id}</td><td>{x.case_id?`#${x.case_id}`:'-'}</td><td>{x.total}</td><td><div className="vilo-table-actions"><Link className="vilo-btn vilo-btn--secondary vilo-btn--xs" href={`/dashboard/invoices/${x.id}`}>View</Link> <button className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={()=>sent(x.id)}>Mark sent</button> <button className="vilo-btn vilo-btn--primary vilo-btn--xs" onClick={()=>paid(x.id)}>Mark paid</button></div></td></tr>)}</tbody></table></div></article> : null}
  </section>;
}
