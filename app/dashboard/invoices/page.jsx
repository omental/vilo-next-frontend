"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

export default function InvoicesPage() {
  const [items, setItems] = useState([]);
  async function load(){ setItems(await apiRequest('/api/v1/invoices')); }
  useEffect(()=>{load();},[]);

  async function sent(id){ await apiRequest(`/api/v1/invoices/${id}/mark-sent`,{method:'PATCH'}); await load(); }
  async function paid(id){ await apiRequest(`/api/v1/invoices/${id}/mark-paid`,{method:'PATCH'}); await load(); }

  return <section className="dashboard-page-stack"><div className="dashboard-page-heading"><h1>Invoices</h1></div>
    <article className="dashboard-card vilo-table-card"><div className="dashboard-card__header"><h2>Invoice List</h2></div><div className="vilo-table-wrap"><table className="team-table"><thead><tr><th>No</th><th>Status</th><th>Client</th><th>Case</th><th>Total</th><th>Actions</th></tr></thead><tbody>{items.map((x)=><tr key={x.id}><td>{x.invoice_number}</td><td><span className={`vilo-badge vilo-badge--${x.status}`}>{x.status}</span></td><td>#{x.client_id}</td><td>{x.case_id?`#${x.case_id}`:'-'}</td><td>{x.total}</td><td><Link href={`/dashboard/invoices/${x.id}`}>View</Link> <button onClick={()=>sent(x.id)}>Mark sent</button> <button onClick={()=>paid(x.id)}>Mark paid</button></td></tr>)}</tbody></table></div></article>
  </section>;
}
