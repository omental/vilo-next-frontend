"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  conversation_type: "internal",
  title: "",
  case_id: "",
  participant_ids: "",
};

function fmtTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

export default function MessagesPage() {
  const [conversations, setConversations] = useState([]);
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [messageBody, setMessageBody] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [composerRefs, setComposerRefs] = useState([]);
  const [caseSearch, setCaseSearch] = useState("");
  const [caseSearchRows, setCaseSearchRows] = useState([]);
  const [showCasePicker, setShowCasePicker] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [meId, setMeId] = useState(null);
  const threadEndRef = useRef(null);

  async function loadConversations() {
    const rows = await apiRequest("/api/v1/conversations");
    setConversations(rows || []);
    setSelected((prev) => {
      if (prev) {
        const next = (rows || []).find((r) => r.id === prev.id);
        return next || ((rows || [])[0] || null);
      }
      return (rows || [])[0] || null;
    });
  }

  async function loadMessages(conversationId) {
    const rows = await apiRequest(`/api/v1/conversations/${conversationId}/messages`);
    setMessages(rows || []);
    await apiRequest(`/api/v1/conversations/${conversationId}/mark-read`, { method: "POST" });
  }

  async function init() {
    setLoading(true);
    setError("");
    try {
      const [caseRows, me] = await Promise.all([apiRequest("/api/v1/cases"), apiRequest("/api/v1/auth/me")]);
      setCases(caseRows || []);
      setMeId(me?.id || null);
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
    loadMessages(selected.id).catch((err) => setError(err.message || "Failed to load messages"));
  }, [selected?.id]);

  useEffect(() => {
    if (!threadEndRef.current) return;
    threadEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, selected?.id]);

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
      setError(err.message || "Failed to create conversation");
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!selected?.id || !messageBody.trim() || sending) return;
    setSending(true);
    setError("");
    try {
      await apiRequest(`/api/v1/conversations/${selected.id}/messages`, {
        method: "POST",
        body: JSON.stringify({
          body: messageBody.trim(),
          parent_message_id: replyTo ? Number(replyTo) : null,
          case_reference_ids: composerRefs.map((c) => c.id),
        }),
      });
      setMessageBody("");
      setReplyTo("");
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
      const rows = await apiRequest(`/api/v1/conversations/cases/search?q=${encodeURIComponent(q)}`);
      setCaseSearchRows(rows || []);
    } catch {
      setCaseSearchRows([]);
    }
  }

  function addCaseRef(row) {
    setComposerRefs((prev) => (prev.some((item) => item.id === row.id) ? prev : [...prev, row]));
    setShowCasePicker(false);
  }

  function onComposerKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  }

  const filteredConversations = useMemo(() => {
    const q = query.trim().toLowerCase();
    return conversations.filter((conv) => {
      if (filter === "unread" && !(conv.unread_count > 0)) return false;
      if (["internal", "client", "group"].includes(filter) && conv.conversation_type !== filter) return false;
      if (!q) return true;
      const blob = `${conv.title || ""} ${conv.latest_message?.body || ""} ${conv.conversation_type || ""}`.toLowerCase();
      return blob.includes(q);
    });
  }, [conversations, filter, query]);

  return (
    <section className="dashboard-page-stack">
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading messages...</p></div> : null}

      <div className="messages-layout">
        <aside className="messages-sidebar dashboard-card">
          <div className="messages-sidebar__head">
            <h2>Messages</h2>
          </div>
          <div className="messages-sidebar__search">
            <input className="case-search-input" placeholder="Search conversations" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="messages-filters">
            {["all", "unread", "internal", "client", "group"].map((key) => (
              <button key={key} type="button" className={filter === key ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setFilter(key)}>
                {key[0].toUpperCase() + key.slice(1)}
              </button>
            ))}
          </div>
          <div className="messages-sidebar__list">
            {!filteredConversations.length ? <p className="vilo-state">No conversations found.</p> : null}
            {filteredConversations.map((conv) => (
              <button key={conv.id} type="button" className={`messages-conversation-item${selected?.id === conv.id ? " is-active" : ""}`} onClick={() => setSelected(conv)}>
                <span className="messages-conversation-item__avatar">{(conv.title || conv.conversation_type || "C").slice(0, 1).toUpperCase()}</span>
                <span className="messages-conversation-item__main">
                  <span className="messages-conversation-item__top">
                    <strong>{conv.title || `${conv.conversation_type} #${conv.id}`}</strong>
                    <small>{fmtTime(conv.latest_message?.created_at || conv.updated_at)}</small>
                  </span>
                  <span className="messages-conversation-item__bottom">
                    <span className={`vilo-badge vilo-badge--${conv.conversation_type === "internal" ? "draft" : conv.conversation_type === "client" ? "active" : "partner"}`}>{conv.conversation_type}</span>
                    <span className="messages-conversation-item__preview">{conv.latest_message?.body || "No messages yet"}</span>
                    {conv.unread_count > 0 ? <em>{conv.unread_count}</em> : null}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <article className="messages-thread dashboard-card">
          {!selected ? <div className="messages-empty"><p className="vilo-state">Select a conversation to start chatting.</p></div> : (
            <>
              <div className="messages-thread__head">
                <div>
                  <h3>{selected.title || `${selected.conversation_type} #${selected.id}`}</h3>
                  <p>{selected.participant_count || 0} participants · {selected.unread_count || 0} unread</p>
                  {selected.case_id ? (
                    <Link href={`/dashboard/cases/${selected.case_id}`} className="message-case-chip">
                      Case: {selected.case_title || `#${selected.case_id}`} ({selected.case_display_number || `CASE${String(selected.case_id).padStart(6, "0")}`})
                    </Link>
                  ) : null}
                </div>
                <span className={`vilo-badge vilo-badge--${selected.conversation_type === "internal" ? "draft" : selected.conversation_type === "client" ? "active" : "partner"}`}>{selected.conversation_type}</span>
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
                              <Link key={`${msg.id}-${ref.case_id}`} href={`/dashboard/cases/${ref.case_id}`} className="message-case-chip">
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
                <input placeholder="Reply to message ID (optional)" value={replyTo} onChange={(e) => setReplyTo(e.target.value)} />
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
                <textarea placeholder="Type message (Enter to send, Shift+Enter new line)" value={messageBody} onChange={(e) => setMessageBody(e.target.value)} onKeyDown={onComposerKeyDown} required />
                <div className="vilo-table-actions">
                  <button
                    type="button"
                    className="vilo-btn vilo-btn--secondary"
                    onClick={async () => {
                      setShowCasePicker(true);
                      if (!caseSearchRows.length) await searchCases("");
                    }}
                  >
                    Link Case
                  </button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={sending || !messageBody.trim()}>{sending ? "Sending..." : "Send"}</button>
                </div>
              </form>
            </>
          )}
        </article>
      </div>

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
          <button type="submit" className="vilo-btn vilo-btn--secondary">Create Conversation</button>
        </form>
      </article>

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
                  placeholder="Search case title or number"
                  value={caseSearch}
                  onChange={async (e) => {
                    const next = e.target.value;
                    setCaseSearch(next);
                    await searchCases(next);
                  }}
                />
                <div className="messages-case-search-list">
                  {!caseSearchRows.length ? <p className="vilo-state">No accessible cases found.</p> : null}
                  {caseSearchRows.map((row) => (
                    <button key={row.id} type="button" className="messages-case-search-item" onClick={() => addCaseRef(row)}>
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
