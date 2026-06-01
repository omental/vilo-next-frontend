"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiRequest } from "../../../lib/api";

function fmtTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

export default function PortalMessagesPage() {
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [body, setBody] = useState("");
  const [composerRefs, setComposerRefs] = useState([]);
  const [showCasePicker, setShowCasePicker] = useState(false);
  const [caseSearch, setCaseSearch] = useState("");
  const [caseRows, setCaseRows] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [meId, setMeId] = useState(null);
  const threadEndRef = useRef(null);

  async function loadConversations() {
    const rows = await apiRequest("/api/v1/portal/messages/conversations");
    setConversations(rows || []);
    setSelected((prev) => {
      if (prev) return (rows || []).find((r) => r.id === prev.id) || ((rows || [])[0] || null);
      return (rows || [])[0] || null;
    });
  }

  async function loadMessages(conversationId) {
    const rows = await apiRequest(`/api/v1/portal/messages/conversations/${conversationId}/messages`);
    setMessages(rows || []);
    await apiRequest(`/api/v1/portal/messages/conversations/${conversationId}/mark-read`, { method: "POST" });
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([loadConversations(), apiRequest("/api/v1/auth/me").then((me) => setMeId(me?.id || null))])
      .catch((err) => setError(err.message || "Failed to load conversations"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected?.id) return;
    loadMessages(selected.id).catch((err) => setError(err.message || "Failed to load messages"));
  }, [selected?.id]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, selected?.id]);

  async function sendMessage(e) {
    e.preventDefault();
    if (!selected?.id || !body.trim() || sending) return;
    setSending(true);
    setError("");
    try {
      await apiRequest(`/api/v1/portal/messages/conversations/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: body.trim(), case_reference_ids: composerRefs.map((c) => c.id) }),
      });
      setBody("");
      setComposerRefs([]);
      await loadConversations();
      await loadMessages(selected.id);
    } catch (err) {
      setError(err.message || "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  async function searchCases(q = "") {
    try {
      const rows = await apiRequest(`/api/v1/portal/messages/case-search?q=${encodeURIComponent(q)}`);
      setCaseRows(rows || []);
    } catch {
      setCaseRows([]);
    }
  }

  function onComposerKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  }

  const filteredConversations = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((conv) => `${conv.title || ""} ${conv.latest_message?.body || ""}`.toLowerCase().includes(q));
  }, [conversations, query]);

  return (
    <section className="dashboard-page-stack">
      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading conversations...</p></div> : null}
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      <div className="messages-layout messages-layout--portal">
        <aside className="messages-sidebar dashboard-card">
          <div className="messages-sidebar__head"><h2>Messages</h2></div>
          <div className="messages-sidebar__search">
            <input className="case-search-input" placeholder="Search conversations" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="messages-sidebar__list">
            {!filteredConversations.length ? <p className="vilo-state">No conversations available.</p> : null}
            {filteredConversations.map((conv) => (
              <button key={conv.id} type="button" className={`messages-conversation-item${selected?.id === conv.id ? " is-active" : ""}`} onClick={() => setSelected(conv)}>
                <span className="messages-conversation-item__avatar">{(conv.title || "C").slice(0, 1).toUpperCase()}</span>
                <span className="messages-conversation-item__main">
                  <span className="messages-conversation-item__top">
                    <strong>{conv.title || `Conversation #${conv.id}`}</strong>
                    <small>{fmtTime(conv.latest_message?.created_at || conv.updated_at)}</small>
                  </span>
                  <span className="messages-conversation-item__bottom">
                    <span className="messages-conversation-item__preview">{conv.latest_message?.body || "No messages yet"}</span>
                    {conv.unread_count > 0 ? <em>{conv.unread_count}</em> : null}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <article className="messages-thread dashboard-card">
          {!selected ? <div className="messages-empty"><p className="vilo-state">Select a conversation.</p></div> : (
            <>
              <div className="messages-thread__head">
                <div>
                  <h3>{selected.title || `Conversation #${selected.id}`}</h3>
                  <p>{selected.unread_count || 0} unread</p>
                  {selected.case_id ? (
                    <Link href={`/portal/cases/${selected.case_id}`} className="message-case-chip">
                      Case: {selected.case_title || `#${selected.case_id}`} ({selected.case_display_number || `CASE${String(selected.case_id).padStart(6, "0")}`})
                    </Link>
                  ) : null}
                </div>
              </div>
              <div className="messages-thread__body">
                {!messages.length ? <p className="vilo-state">No messages yet.</p> : null}
                {messages.map((msg) => {
                  const mine = meId && Number(msg.sender_id) === Number(meId);
                  return (
                    <div key={msg.id} className={`message-bubble-row${mine ? " is-mine" : ""}`}>
                      <div className={`message-bubble${mine ? " is-mine" : ""}`}>
                        {!mine ? <small className="message-bubble__sender">{msg.sender_name || `User #${msg.sender_id}`}</small> : null}
                        <p>{msg.body}</p>
                        {msg.case_references?.length ? (
                          <div className="message-bubble__refs">
                            {msg.case_references.map((ref) => (
                              <Link key={`${msg.id}-${ref.case_id}`} href={`/portal/cases/${ref.case_id}`} className="message-case-chip">
                                Case: {ref.case_title} ({ref.case_display_number || `#${ref.case_id}`})
                              </Link>
                            ))}
                          </div>
                        ) : null}
                        <span>{fmtTime(msg.created_at)}</span>
                      </div>
                    </div>
                  );
                })}
                <div ref={threadEndRef} />
              </div>
              <form className="messages-thread__composer" onSubmit={sendMessage}>
                {composerRefs.length ? (
                  <div className="message-composer-refs">
                    {composerRefs.map((row) => (
                      <span key={row.id} className="message-case-chip">
                        Case: {row.title} ({row.display_number || `#${row.id}`})
                        <button type="button" onClick={() => setComposerRefs((prev) => prev.filter((item) => item.id !== row.id))}>×</button>
                      </span>
                    ))}
                  </div>
                ) : null}
                <textarea placeholder="Type message (Enter to send)" value={body} onChange={(e) => setBody(e.target.value)} onKeyDown={onComposerKeyDown} required />
                <div className="vilo-table-actions">
                  <button
                    type="button"
                    className="vilo-btn vilo-btn--secondary"
                    onClick={async () => {
                      setShowCasePicker(true);
                      if (!caseRows.length) await searchCases("");
                    }}
                  >
                    Link Case
                  </button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={sending || !body.trim()}>{sending ? "Sending..." : "Send"}</button>
                </div>
              </form>
            </>
          )}
        </article>
      </div>

      {showCasePicker ? (
        <div className="vilo-modal-overlay" onClick={() => setShowCasePicker(false)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Link Case</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setShowCasePicker(false)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <div className="vilo-form-grid">
                <input
                  placeholder="Search your cases"
                  value={caseSearch}
                  onChange={async (e) => {
                    const next = e.target.value;
                    setCaseSearch(next);
                    await searchCases(next);
                  }}
                />
                <div className="messages-case-search-list">
                  {!caseRows.length ? <p className="vilo-state">No accessible cases found.</p> : null}
                  {caseRows.map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      className="messages-case-search-item"
                      onClick={() => {
                        setComposerRefs((prev) => (prev.some((item) => item.id === row.id) ? prev : [...prev, row]));
                        setShowCasePicker(false);
                      }}
                    >
                      <strong>{row.title}</strong>
                      <span>{row.display_number || `#${row.id}`}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
