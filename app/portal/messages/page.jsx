"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../../lib/api";

export default function PortalMessagesPage() {
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadConversations() {
    const rows = await apiRequest("/api/v1/portal/messages/conversations");
    setConversations(rows);
    if (!selected && rows.length) setSelected(rows[0]);
  }

  async function loadMessages(conversationId) {
    const rows = await apiRequest(`/api/v1/portal/messages/conversations/${conversationId}/messages`);
    setMessages(rows);
    await apiRequest(`/api/v1/portal/messages/conversations/${conversationId}/mark-read`, { method: "POST" });
  }

  useEffect(() => {
    setLoading(true);
    loadConversations().catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected?.id) return;
    loadMessages(selected.id).catch((err) => setError(err.message));
  }, [selected?.id]);

  async function sendMessage(e) {
    e.preventDefault();
    if (!selected?.id || !body.trim()) return;
    try {
      await apiRequest(`/api/v1/portal/messages/conversations/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setBody("");
      await loadConversations();
      await loadMessages(selected.id);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Messages</h1></div>
      {loading ? <p className="vilo-state">Loading conversations...</p> : null}
      {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}

      <div className="vilo-two-col-grid">
        <article className="dashboard-card vilo-table-card">
          <div className="dashboard-card__header"><h2>Conversations</h2></div>
          {!conversations.length ? <p className="vilo-state">No conversations available.</p> : (
            <ul className="vilo-simple-list">
              {conversations.map((conv) => (
                <li key={conv.id}>
                  <button onClick={() => setSelected(conv)}>
                    {conv.title || `Conversation #${conv.id}`} ({conv.unread_count} unread)
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
                    </li>
                  ))}
                </ul>
              )}
              <form className="vilo-form-grid" onSubmit={sendMessage}>
                <textarea placeholder="Type message" value={body} onChange={(e) => setBody(e.target.value)} required />
                <button type="submit">Send</button>
              </form>
            </>
          )}
        </article>
      </div>
    </section>
  );
}
