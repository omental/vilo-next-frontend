"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const accForm = { name: "", bank_name: "", account_number_last4: "", status: "active" };
const txnForm = { trust_account_id: "", client_id: "", case_id: "", amount: "", description: "", transaction_date: "" };
const applyForm = { trust_account_id: "", client_id: "", case_id: "", invoice_id: "", amount: "", description: "" };

export default function TrustPage() {
  const [accounts, setAccounts] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [txns, setTxns] = useState([]);
  const [clients, setClients] = useState([]);
  const [cases, setCases] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [summary, setSummary] = useState(null);
  const [aForm, setAForm] = useState(accForm);
  const [dForm, setDForm] = useState(txnForm);
  const [rForm, setRForm] = useState(txnForm);
  const [xForm, setXForm] = useState(txnForm);
  const [apForm, setApForm] = useState(applyForm);

  async function load() {
    const [a, l, t, c, cs, i, s] = await Promise.all([
      apiRequest('/api/v1/trust/accounts'), apiRequest('/api/v1/trust/ledgers'), apiRequest('/api/v1/trust/transactions'),
      apiRequest('/api/v1/clients'), apiRequest('/api/v1/cases'), apiRequest('/api/v1/invoices'), apiRequest('/api/v1/trust/reconciliation-summary'),
    ]);
    setAccounts(a); setLedgers(l); setTxns(t); setClients(c); setCases(cs); setInvoices(i); setSummary(s);
  }
  useEffect(()=>{load();},[]);

  async function createAccount(e){ e.preventDefault(); await apiRequest('/api/v1/trust/accounts',{method:'POST', body: JSON.stringify(aForm)}); setAForm(accForm); await load(); }
  async function submit(path, form, reset){ await apiRequest(path,{method:'POST', body: JSON.stringify({...form, trust_account_id:Number(form.trust_account_id), client_id:Number(form.client_id), case_id:form.case_id?Number(form.case_id):null, amount:Number(form.amount)})}); reset(txnForm); await load(); }
  async function applyTrust(e){ e.preventDefault(); await apiRequest('/api/v1/trust/apply-to-invoice',{method:'POST', body: JSON.stringify({...apForm, trust_account_id:Number(apForm.trust_account_id), client_id:Number(apForm.client_id), case_id:apForm.case_id?Number(apForm.case_id):null, invoice_id:Number(apForm.invoice_id), amount:Number(apForm.amount)})}); setApForm(applyForm); await load(); }

  const optionRows = (arr, label) => arr.map((x)=><option key={x.id} value={x.id}>{label(x)}</option>);

  return <section className="dashboard-page-stack">
    <div className="dashboard-page-heading"><h1>Trust Accounting</h1></div>

    <article className="dashboard-card vilo-form-card"><div className="dashboard-card__header"><h2>Create Trust Account</h2></div>
      <form className="vilo-form-grid" onSubmit={createAccount}>
        <input placeholder="Name" value={aForm.name} onChange={(e)=>setAForm({...aForm,name:e.target.value})} required />
        <input placeholder="Bank Name" value={aForm.bank_name} onChange={(e)=>setAForm({...aForm,bank_name:e.target.value})} />
        <input placeholder="Last 4" maxLength={4} value={aForm.account_number_last4} onChange={(e)=>setAForm({...aForm,account_number_last4:e.target.value})} />
        <button type="submit">Create Account</button>
      </form>
    </article>

    <article className="dashboard-card vilo-form-card"><div className="dashboard-card__header"><h2>Record Deposit</h2></div>
      <form className="vilo-form-grid" onSubmit={(e)=>{e.preventDefault(); submit('/api/v1/trust/deposit', dForm, setDForm);}}>
        <div className="vilo-form-row-two"><select value={dForm.trust_account_id} onChange={(e)=>setDForm({...dForm,trust_account_id:e.target.value})} required><option value="">Account</option>{optionRows(accounts,(a)=>a.name)}</select><select value={dForm.client_id} onChange={(e)=>setDForm({...dForm,client_id:e.target.value})} required><option value="">Client</option>{optionRows(clients,(c)=>c.name)}</select></div>
        <div className="vilo-form-row-two"><select value={dForm.case_id} onChange={(e)=>setDForm({...dForm,case_id:e.target.value})}><option value="">Case (optional)</option>{optionRows(cases,(c)=>c.title)}</select><input type="number" step="0.01" placeholder="Amount" value={dForm.amount} onChange={(e)=>setDForm({...dForm,amount:e.target.value})} required/></div>
        <input type="date" value={dForm.transaction_date} onChange={(e)=>setDForm({...dForm,transaction_date:e.target.value})} required />
        <input placeholder="Description" value={dForm.description} onChange={(e)=>setDForm({...dForm,description:e.target.value})} />
        <button type="submit">Deposit</button>
      </form>
    </article>

    <article className="dashboard-card vilo-form-card"><div className="dashboard-card__header"><h2>Refund / Disbursement / Apply to Invoice</h2></div>
      <form className="vilo-form-grid" onSubmit={(e)=>{e.preventDefault(); submit('/api/v1/trust/refund', rForm, setRForm);}}><h3>Refund</h3><div className="vilo-form-row-two"><select value={rForm.trust_account_id} onChange={(e)=>setRForm({...rForm,trust_account_id:e.target.value})} required><option value="">Account</option>{optionRows(accounts,(a)=>a.name)}</select><select value={rForm.client_id} onChange={(e)=>setRForm({...rForm,client_id:e.target.value})} required><option value="">Client</option>{optionRows(clients,(c)=>c.name)}</select></div><input type="number" step="0.01" placeholder="Amount" value={rForm.amount} onChange={(e)=>setRForm({...rForm,amount:e.target.value})} required/><input type="date" value={rForm.transaction_date} onChange={(e)=>setRForm({...rForm,transaction_date:e.target.value})} required /><button type="submit">Refund</button></form>
      <form className="vilo-form-grid" onSubmit={(e)=>{e.preventDefault(); submit('/api/v1/trust/disbursement', xForm, setXForm);}}><h3>Disbursement</h3><div className="vilo-form-row-two"><select value={xForm.trust_account_id} onChange={(e)=>setXForm({...xForm,trust_account_id:e.target.value})} required><option value="">Account</option>{optionRows(accounts,(a)=>a.name)}</select><select value={xForm.client_id} onChange={(e)=>setXForm({...xForm,client_id:e.target.value})} required><option value="">Client</option>{optionRows(clients,(c)=>c.name)}</select></div><input type="number" step="0.01" placeholder="Amount" value={xForm.amount} onChange={(e)=>setXForm({...xForm,amount:e.target.value})} required/><input type="date" value={xForm.transaction_date} onChange={(e)=>setXForm({...xForm,transaction_date:e.target.value})} required /><button type="submit">Disburse</button></form>
      <form className="vilo-form-grid" onSubmit={applyTrust}><h3>Apply to Invoice</h3><div className="vilo-form-row-two"><select value={apForm.trust_account_id} onChange={(e)=>setApForm({...apForm,trust_account_id:e.target.value})} required><option value="">Account</option>{optionRows(accounts,(a)=>a.name)}</select><select value={apForm.client_id} onChange={(e)=>setApForm({...apForm,client_id:e.target.value})} required><option value="">Client</option>{optionRows(clients,(c)=>c.name)}</select></div><div className="vilo-form-row-two"><select value={apForm.case_id} onChange={(e)=>setApForm({...apForm,case_id:e.target.value})}><option value="">Case (optional)</option>{optionRows(cases,(c)=>c.title)}</select><select value={apForm.invoice_id} onChange={(e)=>setApForm({...apForm,invoice_id:e.target.value})} required><option value="">Invoice</option>{optionRows(invoices,(i)=>i.invoice_number)}</select></div><input type="number" step="0.01" placeholder="Amount" value={apForm.amount} onChange={(e)=>setApForm({...apForm,amount:e.target.value})} required/><button type="submit">Apply</button></form>
    </article>

    {summary ? <article className="dashboard-card vilo-detail-card"><div className="dashboard-card__header"><h2>Reconciliation Summary</h2></div><p className="vilo-card-copy">Trust: {summary.total_trust_account_balance} | Client Ledgers: {summary.total_client_ledger_balances} | Matter Balances: {summary.total_matter_case_balances} | Match: {summary.matches ? 'Yes':'No'}</p></article> : null}

    <article className="dashboard-card vilo-table-card"><div className="dashboard-card__header"><h2>Ledger Balances</h2></div><div className="vilo-table-wrap"><table className="team-table"><thead><tr><th>Account</th><th>Client</th><th>Case</th><th>Balance</th></tr></thead><tbody>{ledgers.map((l)=><tr key={l.id}><td>#{l.trust_account_id}</td><td>#{l.client_id}</td><td>{l.case_id?`#${l.case_id}`:'-'}</td><td>{l.current_balance}</td></tr>)}</tbody></table></div></article>
    <article className="dashboard-card vilo-table-card"><div className="dashboard-card__header"><h2>Recent Trust Transactions</h2></div><div className="vilo-table-wrap"><table className="team-table"><thead><tr><th>Type</th><th>Amount</th><th>Date</th><th>Client</th><th>Case</th></tr></thead><tbody>{txns.map((t)=><tr key={t.id}><td>{t.transaction_type}</td><td>{t.amount}</td><td>{t.transaction_date}</td><td>#{t.client_id}</td><td>{t.case_id?`#${t.case_id}`:'-'}</td></tr>)}</tbody></table></div></article>
  </section>
}
