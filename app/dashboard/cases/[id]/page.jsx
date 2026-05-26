"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiRequest } from "../../../../lib/api";
import { getToken } from "../../../../lib/auth";

export default function CaseDetailPage() {
  const { id } = useParams();
  const [item, setItem] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [notes, setNotes] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [convForm, setConvForm] = useState({ conversation_type: "internal", title: "", participant_ids: "" });
  const [timeEntries, setTimeEntries] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [trustTxns, setTrustTxns] = useState([]);
  const [trustLedgers, setTrustLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [docForm, setDocForm] = useState({ title: "", description: "", category: "", file: null });
  const [noteForm, setNoteForm] = useState({ note: "", visibility: "internal" });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [caseData, taskData, eventData, docData, noteData, timelineData, timeEntryData, expenseData, invoiceData, trustTxnData, trustLedgerData, conversationData] = await Promise.all([
        apiRequest(`/api/v1/cases/${id}`),
        apiRequest(`/api/v1/tasks?case_id=${id}`),
        apiRequest(`/api/v1/calendar/events?case_id=${id}`),
        apiRequest(`/api/v1/documents?case_id=${id}`),
        apiRequest(`/api/v1/cases/${id}/notes`),
        apiRequest(`/api/v1/cases/${id}/timeline`),
        apiRequest(`/api/v1/time-entries?case_id=${id}`),
        apiRequest(`/api/v1/expenses?case_id=${id}`),
        apiRequest(`/api/v1/invoices`).then((all)=>all.filter((i)=>String(i.case_id)===String(id))),
        apiRequest(`/api/v1/trust/transactions`).then((all)=>all.filter((t)=>String(t.case_id)===String(id))).catch(()=>[]),
        apiRequest(`/api/v1/trust/ledgers`).then((all)=>all.filter((l)=>String(l.case_id)===String(id))).catch(()=>[]),
        apiRequest(`/api/v1/conversations`).then((all)=>all.filter((c)=>String(c.case_id)===String(id))).catch(()=>[]),
      ]);
      setItem(caseData);
      setTasks(taskData);
      setEvents(eventData);
      setDocuments(docData);
      setNotes(noteData);
      setTimeline(timelineData);
      setTimeEntries(timeEntryData);
      setExpenses(expenseData);
      setInvoices(invoiceData);
      setTrustTxns(trustTxnData);
      setTrustLedgers(trustLedgerData);
      setConversations(conversationData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  async function uploadDocument(e) {
    e.preventDefault();
    setError("");
    if (!docForm.file) return setError("Please choose a file");
    const fd = new FormData();
    fd.append("title", docForm.title);
    if (docForm.description) fd.append("description", docForm.description);
    if (docForm.category) fd.append("category", docForm.category);
    fd.append("case_id", String(id));
    fd.append("file", docForm.file);

    const token = getToken();
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/v1/documents/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Upload failed");
      return;
    }
    setDocForm({ title: "", description: "", category: "", file: null });
    await load();
  }

  async function addNote(e) {
    e.preventDefault();
    setError("");
    await apiRequest(`/api/v1/cases/${id}/notes`, {
      method: "POST",
      body: JSON.stringify(noteForm),
    });
    setNoteForm({ note: "", visibility: "internal" });
    await load();
  }

  

  async function createCaseConversation(e) {
    e.preventDefault();
    setError("");
    const participant_ids = convForm.participant_ids.split(",").map((x)=>x.trim()).filter(Boolean).map(Number);
    await apiRequest(`/api/v1/conversations`, {
      method: "POST",
      body: JSON.stringify({
        conversation_type: convForm.conversation_type,
        title: convForm.title || null,
        case_id: Number(id),
        participant_ids,
      }),
    });
    setConvForm({ conversation_type: "internal", title: "", participant_ids: "" });
    await load();
  }

  async function generateInvoiceFromCase() {
    await apiRequest(`/api/v1/invoices/generate-from-case/${id}`, { method: "POST" });
    await load();
  }

  function downloadDocument(documentId) {
    const token = getToken();
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    fetch(`${base}/api/v1/documents/${documentId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Download failed");
        const blob = await r.blob();
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = "document";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(href);
      })
      .catch((err) => setError(err.message));
  }

  return (
    <section className="dashboard-page-stack">
      <div className="vilo-inline-actions">
        <Link href="/dashboard/cases" className="vilo-back-link">Back to cases</Link>
      </div>

      {loading ? <p className="vilo-state">Loading case...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      {item ? (
        <>
          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>{item.title}</h2></div>
            <div className="vilo-detail-grid">
              <p><strong>Status:</strong> <span className={`vilo-badge vilo-badge--${item.status}`}>{item.status}</span></p>
              <p><strong>Priority:</strong> <span className={`vilo-badge vilo-badge--priority-${item.priority}`}>{item.priority}</span></p>
              <p><strong>Client ID:</strong> #{item.client_id}</p>
              <p><strong>Created by:</strong> User #{item.created_by}</p>
            </div>
            <p className="vilo-card-copy"><strong>Description:</strong> {item.description || "No description provided."}</p>
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Linked Tasks</h2></div>
            {tasks.length === 0 ? <p className="vilo-card-copy">No tasks linked to this case.</p> : (
              <ul className="vilo-simple-list">
                {tasks.map((task) => <li key={task.id}>{task.title} - <span className={`vilo-badge vilo-badge--${task.status}`}>{task.status}</span></li>)}
              </ul>
            )}
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Linked Events</h2></div>
            {events.length === 0 ? <p className="vilo-card-copy">No calendar events linked to this case.</p> : (
              <ul className="vilo-simple-list">
                {events.map((event) => <li key={event.id}>{event.title} ({event.event_type}) - {new Date(event.start_at).toLocaleString()}</li>)}
              </ul>
            )}
          </article>

          <article className="dashboard-card vilo-form-card">
            <div className="dashboard-card__header"><h2>Upload Case Document</h2></div>
            <form className="vilo-form-grid" onSubmit={uploadDocument}>
              <input placeholder="Title" value={docForm.title} onChange={(e) => setDocForm({ ...docForm, title: e.target.value })} required />
              <textarea placeholder="Description" value={docForm.description} onChange={(e) => setDocForm({ ...docForm, description: e.target.value })} />
              <input placeholder="Category" value={docForm.category} onChange={(e) => setDocForm({ ...docForm, category: e.target.value })} />
              <input type="file" onChange={(e) => setDocForm({ ...docForm, file: e.target.files?.[0] || null })} required />
              <button type="submit">Upload</button>
            </form>
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Case Documents</h2></div>
            {documents.length === 0 ? <p className="vilo-card-copy">No documents linked to this case.</p> : (
              <ul className="vilo-simple-list">
                {documents.map((doc) => (
                  <li key={doc.id}>
                    {doc.title} ({doc.file_name})
                    <button onClick={() => downloadDocument(doc.id)} style={{ marginLeft: 8 }}>Download</button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="dashboard-card vilo-form-card">
            <div className="dashboard-card__header"><h2>Add Case Note</h2></div>
            <form className="vilo-form-grid" onSubmit={addNote}>
              <textarea placeholder="Write note" value={noteForm.note} onChange={(e) => setNoteForm({ ...noteForm, note: e.target.value })} required />
              <select value={noteForm.visibility} onChange={(e) => setNoteForm({ ...noteForm, visibility: e.target.value })}>
                <option value="internal">internal</option>
                <option value="client_visible">client_visible</option>
              </select>
              <button type="submit">Add Note</button>
            </form>
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Case Notes</h2></div>
            {notes.length === 0 ? <p className="vilo-card-copy">No notes yet.</p> : (
              <ul className="vilo-simple-list">
                {notes.map((n) => (
                  <li key={n.id}>
                    <div>{n.note}</div>
                    <div>
                      <span className={`vilo-badge ${n.visibility === "internal" ? "vilo-badge--draft" : "vilo-badge--closed"}`}>{n.visibility}</span>
                      <span style={{ marginLeft: 8 }}>by User #{n.created_by} • {new Date(n.created_at).toLocaleString()}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </article>



          <article className="dashboard-card vilo-form-card">
            <div className="dashboard-card__header"><h2>Case Conversations</h2></div>
            <form className="vilo-form-grid" onSubmit={createCaseConversation}>
              <div className="vilo-form-row-two">
                <select value={convForm.conversation_type} onChange={(e) => setConvForm({ ...convForm, conversation_type: e.target.value })}>
                  <option value="internal">internal</option>
                  <option value="client">client</option>
                  <option value="group">group</option>
                </select>
                <input placeholder="Participant user IDs (comma separated)" value={convForm.participant_ids} onChange={(e) => setConvForm({ ...convForm, participant_ids: e.target.value })} />
              </div>
              <input placeholder="Conversation title" value={convForm.title} onChange={(e) => setConvForm({ ...convForm, title: e.target.value })} />
              <button type="submit">Start Conversation</button>
            </form>
            {conversations.length ? <ul className="vilo-simple-list">{conversations.map((c)=><li key={c.id}>{c.title || `${c.conversation_type} #${c.id}`} ({c.unread_count} unread)</li>)}</ul> : <p className="vilo-card-copy">No conversations linked to this case yet.</p>}
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Billing</h2></div>
            <p className="vilo-card-copy"><button onClick={generateInvoiceFromCase}>Generate Invoice From Case</button></p>
            <p className="vilo-card-copy">Time Entries: {timeEntries.length} | Expenses: {expenses.length} | Invoices: {invoices.length}</p>
            {invoices.length ? <ul className="vilo-simple-list">{invoices.map((i)=><li key={i.id}>{i.invoice_number} - {i.status} - {i.total}</li>)}</ul> : null}
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Trust Balance</h2></div>
            <p className="vilo-card-copy">Case trust ledgers: {trustLedgers.length}</p>
            {trustLedgers.length ? <ul className="vilo-simple-list">{trustLedgers.map((l)=><li key={l.id}>Account #{l.trust_account_id} • Balance {l.current_balance}</li>)}</ul> : <p className="vilo-card-copy">No trust ledger balance for this case.</p>}
            {trustTxns.length ? <ul className="vilo-simple-list">{trustTxns.map((t)=><li key={t.id}>{t.transaction_type} • {t.amount} • {t.transaction_date}</li>)}</ul> : null}
          </article>

          <article className="dashboard-card vilo-detail-card">
            <div className="dashboard-card__header"><h2>Case Timeline</h2></div>
            {timeline.length === 0 ? <p className="vilo-card-copy">No timeline activity yet.</p> : (
              <ul className="vilo-simple-list">
                {timeline.map((entry) => (
                  <li key={entry.id}>
                    <strong>{entry.title}</strong>
                    <div>{entry.event_type} • {new Date(entry.created_at).toLocaleString()}</div>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
}
