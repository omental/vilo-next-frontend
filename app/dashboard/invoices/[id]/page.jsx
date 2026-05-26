"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiDownload, apiRequest } from "../../../../lib/api";

export default function InvoiceDetailPage(){
  const {id}=useParams();
  const [inv,setInv]=useState(null);
  const [sum,setSum]=useState(null);
  const [trusts,setTrusts]=useState([]);
  const [applyForm,setApplyForm]=useState({trust_account_id:"", amount:"", description:""});

  async function load(){
    const [a,b,c]=await Promise.all([
      apiRequest(`/api/v1/invoices/${id}`),
      apiRequest(`/api/v1/invoices/${id}/summary`),
      apiRequest('/api/v1/trust/accounts').catch(()=>[])
    ]);
    setInv(a); setSum(b); setTrusts(c);
  }
  useEffect(()=>{load();},[id]);

  async function applyTrust(e){
    e.preventDefault();
    await apiRequest('/api/v1/trust/apply-to-invoice',{method:'POST', body: JSON.stringify({
      trust_account_id:Number(applyForm.trust_account_id),
      client_id:Number(inv.client_id),
      case_id:inv.case_id ?? null,
      invoice_id:Number(id),
      amount:Number(applyForm.amount),
      description:applyForm.description || null,
    })});
    setApplyForm({...applyForm, amount:"", description:""});
    await load();
  }

  if(!inv) return <p className="vilo-state">Loading invoice...</p>;
  return <section className="dashboard-page-stack"><div className="dashboard-page-heading"><h1>Invoice {inv.invoice_number}</h1></div>
    <article className="dashboard-card vilo-form-card">
      <button type="button" onClick={()=>apiDownload(`/api/v1/invoices/${id}/pdf`)}>Download PDF</button>
    </article>
    <article className="dashboard-card vilo-detail-card"><div className="dashboard-card__header"><h2>Summary</h2></div><div className="vilo-detail-grid"><p><strong>Status:</strong> {inv.status}</p><p><strong>Client:</strong> #{inv.client_id}</p><p><strong>Case:</strong> {inv.case_id?`#${inv.case_id}`:'-'}</p><p><strong>Total:</strong> {inv.total}</p><p><strong>Paid:</strong> {inv.paid_amount}</p><p><strong>Balance Due:</strong> {inv.balance_due}</p></div></article>
    <article className="dashboard-card vilo-table-card"><div className="dashboard-card__header"><h2>Line Items</h2></div><div className="vilo-table-wrap"><table className="team-table"><thead><tr><th>Type</th><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{inv.line_items.map((li)=><tr key={li.id}><td>{li.line_type}</td><td>{li.description}</td><td>{li.quantity}</td><td>{li.unit_price}</td><td>{li.amount}</td></tr>)}</tbody></table></div></article>
    {sum?<article className="dashboard-card vilo-detail-card"><div className="dashboard-card__header"><h2>Calculated Totals</h2></div><p className="vilo-card-copy">Subtotal: {sum.subtotal} | Tax: {sum.tax_amount} | Total: {sum.total} | Paid: {sum.paid_amount} | Due: {sum.balance_due}</p></article>:null}
    <article className="dashboard-card vilo-form-card"><div className="dashboard-card__header"><h2>Apply Trust Funds</h2></div>
      <form className="vilo-form-grid" onSubmit={applyTrust}>
        <select value={applyForm.trust_account_id} onChange={(e)=>setApplyForm({...applyForm,trust_account_id:e.target.value})} required><option value="">Trust Account</option>{trusts.map((t)=><option key={t.id} value={t.id}>{t.name}</option>)}</select>
        <input type="number" step="0.01" placeholder="Amount" value={applyForm.amount} onChange={(e)=>setApplyForm({...applyForm,amount:e.target.value})} required />
        <input placeholder="Description" value={applyForm.description} onChange={(e)=>setApplyForm({...applyForm,description:e.target.value})} />
        <button type="submit">Apply Trust</button>
      </form>
    </article>
  </section>
}
