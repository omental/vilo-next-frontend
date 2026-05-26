"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  conversation_type: "internal",
  title: "",
  case_id: "",
  participant_ids: "",
};

export default function MessagesPage() {
  const [conversations, setConversations] = useState([]);
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [messageBody, setMessageBody] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadConversations() {
    const rows = await apiRequest("/api/v1/conversations");
    setConversations(rows);
    if (!selected && rows.length) setSelected(rows[0]);
  }

  async function loadMessages(conversationId) {
    const rows = await apiRequest(`/api/v1/conversations/${conversationId}/messages`);
    setMessages(rows);
    await apiRequest(`/api/v1/conversations/${conversationId}/mark-read`, { method: "POST" });
  }

  async function init() {
    setLoading(true);
    setError("");
    try {
      const [caseRows] = await Promise.all([apiRequest("/api/v1/cases")]);
      setCases(caseRows);
      await loadConversations();
    } catch (err) {
      setError(err.message || "Failed to load messaging workspace");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    init();
  }, []);

  useEffect(() => {
    if (!selected?.id) return;
    loadMessages(selected.id).catch((err) => setError(err.message));
  }, [selected?.id]);

  async function createConversation(e) {
    e.preventDefault();
    setError("");
    try {
      const participant_ids = form.participant_ids
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean)
        .map(Number);
      const created = await apiRequest("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({
          conversation_type: form.conversation_type,
          title: form.title || null,
          case_id: form.case_id ? Number(form.case_id) : null,
          participant_ids,
        }),
      });
      setForm(initialForm);
      await loadConversations();
      setSelected(created);
    } catch (err) {
      setError(err.message);
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!selected?.id || !messageBody.trim()) return;
    setError("");
    try {
      await apiRequest(`/api/v1/conversations/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: messageBody, parent_message_id: replyTo ? Number(replyTo) : null }),
      });
      setMessageBody("");
      setReplyTo("");
      await loadConversations();
      await loadMessages(selected.id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Messages</h1></div>
      {loading ? <p className="vilo-state">Loading messages...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Create Conversation</h2></div>
        <form className="vilo-form-grid" onSubmit={createConversation}>
          <div className="vilo-form-row-two">
            <select value={form.conversation_type} onChange={(e) => setForm({ ...form, conversation_type: e.target.value })}>
              <option value="internal">internal</option>
              <option value="client">client</option>
              <option value="group">group</option>
            </select>
            <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
              <option value="">No case link</option>
              {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </div>
          <input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input placeholder="Participant user IDs (comma separated)" value={form.participant_ids} onChange={(e) => setForm({ ...form, participant_ids: e.target.value })} />
          <button type="submit">Create Conversation</button>
        </form>
      </article>

      <div className="vilo-two-col-grid">
        <article className="dashboard-card vilo-table-card">
          <div className="dashboard-card__header"><h2>Conversations</h2></div>
          {!conversations.length ? <p className="vilo-state">No conversations yet.</p> : (
            <ul className="vilo-simple-list">
              {conversations.map((conv) => (
                <li key={conv.id}>
                  <button onClick={() => setSelected(conv)}>
                    {conv.title || `${conv.conversation_type} #${conv.id}`} ({conv.unread_count} unread)
                  </button>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="dashboard-card vilo-table-card">
          <div className="dashboard-card__header"><h2>Thread</h2></div>
          {!selected ? <p className="vilo-state">Select a conversation.</p> : (
            <>
              {!messages.length ? <p className="vilo-state">No messages yet.</p> : (
                <ul className="vilo-simple-list">
                  {messages.map((msg) => (
                    <li key={msg.id}>
                      <div><strong>User #{msg.sender_id}</strong> {new Date(msg.created_at).toLocaleString()}</div>
                      <div>{msg.body}</div>
                      {msg.parent_message_id ? <small>Reply to #{msg.parent_message_id}</small> : null}
                    </li>
                  ))}
                </ul>
              )}
              <form className="vilo-form-grid" onSubmit={sendMessage}>
                <input placeholder="Reply to message ID (optional)" value={replyTo} onChange={(e) => setReplyTo(e.target.value)} />
                <textarea placeholder="Type message" value={messageBody} onChange={(e) => setMessageBody(e.target.value)} required />
                <button type="submit">Send</button>
              </form>
            </>
          )}
        </article>
      </div>
    </section>
  );
}
