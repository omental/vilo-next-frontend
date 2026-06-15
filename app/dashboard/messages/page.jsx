"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  conversation_type: "internal",
  title: "",
  case_id: "",
  participant_ids: "",
};

function formatConversationTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function formatBubbleTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDayLabel(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return "Today";
  return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

function sameDay(left, right) {
  return new Date(left).toDateString() === new Date(right).toDateString();
}

function getInitials(value) {
  const source = String(value || "Message").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function conversationSubtitle(conv) {
  if (conv.case_title) return conv.case_title;
  if (conv.conversation_type === "client") return "Client conversation";
  if (conv.conversation_type === "group") return `${conv.participant_count || 0} participants`;
  return "Internal conversation";
}

function conversationLabel(conv) {
  return conv.title || `${conv.conversation_type} #${conv.id}`;
}

function IconBase({ children }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

function SearchIcon() {
  return (
    <IconBase>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </IconBase>
  );
}

function VideoIcon() {
  return (
    <IconBase>
      <rect x="3" y="6" width="12" height="12" rx="3" />
      <path d="m15 10 5-3v10l-5-3" />
    </IconBase>
  );
}

function PhoneIcon() {
  return (
    <IconBase>
      <path d="M6.6 4.8h2.6l1.2 3.4-1.6 1.5a14.5 14.5 0 0 0 5.5 5.5l1.5-1.6 3.4 1.2v2.6a1.5 1.5 0 0 1-1.7 1.5C10.4 18 6 13.6 5.1 6.5A1.5 1.5 0 0 1 6.6 4.8Z" />
    </IconBase>
  );
}

function DotsIcon() {
  return (
    <IconBase>
      <path d="M5 12h.01" />
      <path d="M12 12h.01" />
      <path d="M19 12h.01" />
    </IconBase>
  );
}

function PaperclipIcon() {
  return (
    <IconBase>
      <path d="m21.4 11.1-8.8 8.8a5 5 0 1 1-7.1-7.1l9.1-9.1a3.5 3.5 0 1 1 5 5l-9.4 9.4a2 2 0 1 1-2.8-2.8l8.4-8.4" />
    </IconBase>
  );
}

function SendIcon() {
  return (
    <IconBase>
      <path d="M22 2 11 13" />
      <path d="m22 2-7 20-4-9-9-4 20-7Z" />
    </IconBase>
  );
}

export default function MessagesPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading messages...</p></div></section>}>
      <MessagesPageContent />
    </Suspense>
  );
}

function MessagesPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [conversations, setConversations] = useState([]);
  const [cases, setCases] = useState([]);
  const [clients, setClients] = useState([]);
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
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [sendError, setSendError] = useState("");
  const [meId, setMeId] = useState(null);
  const threadEndRef = useRef(null);
  const requestedClientId = Number(searchParams.get("client_id") || 0);

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
    setMessagesLoading(true);
    try {
      const rows = await apiRequest(`/api/v1/conversations/${conversationId}/messages`);
      setMessages(rows || []);
      await apiRequest(`/api/v1/conversations/${conversationId}/mark-read`, { method: "POST" });
    } finally {
      setMessagesLoading(false);
    }
  }

  async function init() {
    setLoading(true);
    setError("");
    try {
      const [caseRows, clientRows, me] = await Promise.all([apiRequest("/api/v1/cases"), apiRequest("/api/v1/clients"), apiRequest("/api/v1/auth/me")]);
      setCases(caseRows || []);
      setClients(clientRows || []);
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
    if (searchParams.get("create") === "1") {
      setShowCreateModal(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("create") !== "1" || !requestedClientId) return;
    const targetClient = clients.find((client) => Number(client.id) === requestedClientId);
    const relatedCase = cases.find((caseRow) => Number(caseRow.client_id) === requestedClientId);
    setForm((current) => ({
      ...current,
      conversation_type: targetClient?.user_id && relatedCase ? "client" : "internal",
      title: current.title || (targetClient ? `Message: ${targetClient.name}` : current.title),
      case_id: relatedCase ? String(relatedCase.id) : "",
      participant_ids: targetClient?.user_id ? String(targetClient.user_id) : "",
    }));
  }, [cases, clients, requestedClientId, searchParams]);

  useEffect(() => {
    const conversationId = Number(searchParams.get("conversation") || 0);
    if (!conversationId || !conversations.length) return;
    const target = conversations.find((row) => Number(row.id) === conversationId);
    if (target) {
      setSelected((prev) => (prev?.id === target.id ? prev : target));
    }
  }, [conversations, searchParams]);

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
      closeCreateModal();
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
    setSendError("");
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
      setSendError(err.message || "Failed to send message");
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
      const blob = `${conv.title || ""} ${conv.latest_message?.body || ""} ${conv.conversation_type || ""} ${conv.case_title || ""}`.toLowerCase();
      return blob.includes(q);
    });
  }, [conversations, filter, query]);

  const selectedTitle = selected ? conversationLabel(selected) : "";
  const selectedSubtitle = selected?.case_title || `${selected?.participant_count || 0} participants`;
  const requestedClient = useMemo(
    () => clients.find((client) => Number(client.id) === requestedClientId) || null,
    [clients, requestedClientId],
  );

  function closeCreateModal() {
    setShowCreateModal(false);
    setForm(initialForm);
    if (searchParams.get("create") !== "1") return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("create");
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname);
  }

  return (
    <section className="dashboard-page-stack">
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading messages...</p></div> : null}

      <div className="messages-shell dashboard-card">
        <div className="messages-layout">
          <aside className="messages-sidebar">
            <div className="messages-sidebar__head">
              <h2>Messages</h2>
              <button type="button" className="vilo-btn vilo-btn--secondary messages-sidebar__new" onClick={() => setShowCreateModal(true)}>
                + New Message
              </button>
            </div>

            <div className="messages-sidebar__search">
              <label className="messages-search-field">
                <SearchIcon />
                <input placeholder="Search conversations" value={query} onChange={(e) => setQuery(e.target.value)} />
              </label>
            </div>

            <div className="messages-filters">
              {["all", "unread", "internal", "client", "group"].map((key) => (
                <button key={key} type="button" className={filter === key ? "case-tab-btn is-active" : "case-tab-btn"} onClick={() => setFilter(key)}>
                  {key[0].toUpperCase() + key.slice(1)}
                </button>
              ))}
            </div>

            <div className="messages-sidebar__list">
              {!filteredConversations.length ? (
                <div className="messages-empty-state">
                  <strong>No conversations</strong>
                  <span>Start a new thread to begin messaging.</span>
                </div>
              ) : null}
              {filteredConversations.map((conv) => (
                <button key={conv.id} type="button" className={`messages-conversation-item${selected?.id === conv.id ? " is-active" : ""}`} onClick={() => setSelected(conv)}>
                  <span className="messages-conversation-item__avatar">{getInitials(conversationLabel(conv))}</span>
                  <span className="messages-conversation-item__main">
                    <span className="messages-conversation-item__top">
                      <strong>{conversationLabel(conv)}</strong>
                      <small>{formatConversationTime(conv.latest_message?.created_at || conv.updated_at)}</small>
                    </span>
                    <span className="messages-conversation-item__meta">{conversationSubtitle(conv)}</span>
                    <span className="messages-conversation-item__bottom">
                      <span className="messages-conversation-item__preview">{conv.latest_message?.body || "No messages yet"}</span>
                      {conv.unread_count > 0 ? <em>{conv.unread_count}</em> : null}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <article className="messages-thread">
            {!selected ? (
              <div className="messages-empty">
                <div className="messages-empty-state messages-empty-state--thread">
                  <strong>No conversation selected</strong>
                  <span>Choose a conversation from the left panel to view the thread.</span>
                </div>
              </div>
            ) : (
              <>
                <div className="messages-thread__head">
                  <div className="messages-thread__identity">
                    <span className="messages-thread__avatar">{getInitials(selectedTitle)}</span>
                    <div>
                      <h3>{selectedTitle}</h3>
                      <p>{selectedSubtitle}</p>
                      {selected.case_id ? (
                        <Link href={`/dashboard/cases/${selected.case_id}`} className="message-case-chip">
                          Case: {selected.case_title || `#${selected.case_id}`} ({selected.case_display_number || `CASE${String(selected.case_id).padStart(6, "0")}`})
                        </Link>
                      ) : null}
                    </div>
                  </div>
                  <div className="messages-thread__actions" aria-label="Message actions">
                    <button type="button" className="messages-icon-button" aria-label="Call feature unavailable" title="Call feature unavailable">
                      <VideoIcon />
                    </button>
                    <button type="button" className="messages-icon-button" aria-label="Phone feature unavailable" title="Phone feature unavailable">
                      <PhoneIcon />
                    </button>
                    <button type="button" className="messages-icon-button" aria-label="More actions unavailable" title="More actions unavailable">
                      <DotsIcon />
                    </button>
                  </div>
                </div>

                <div className="messages-thread__body">
                  {messagesLoading ? (
                    <div className="messages-empty-state messages-empty-state--thread">
                      <strong>Loading messages</strong>
                      <span>Fetching the latest thread history.</span>
                    </div>
                  ) : null}
                  {!messagesLoading && !messages.length ? (
                    <div className="messages-empty-state messages-empty-state--thread">
                      <strong>No messages yet</strong>
                      <span>Send the first message to start this conversation.</span>
                    </div>
                  ) : null}
                  {!messagesLoading ? messages.map((msg, index) => {
                    const mine = meId && Number(msg.sender_id) === Number(meId);
                    const showDay = index === 0 || !sameDay(messages[index - 1]?.created_at, msg.created_at);
                    return (
                      <div key={msg.id}>
                        {showDay ? <div className="messages-day-separator"><span>{formatDayLabel(msg.created_at)}</span></div> : null}
                        <div className={`message-bubble-row${mine ? " is-mine" : ""}`}>
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
                            <span className="message-bubble__time">{formatBubbleTime(msg.created_at)}</span>
                          </div>
                        </div>
                      </div>
                    );
                  }) : null}
                  <div ref={threadEndRef} />
                </div>

                <form className="messages-thread__composer" onSubmit={sendMessage}>
                  {replyTo ? <div className="messages-reply-indicator">Replying to message #{replyTo}</div> : null}
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
                  <div className="messages-composer__main">
                    <div className="messages-composer__input-wrap">
                      <textarea
                        placeholder="Write a message..."
                        value={messageBody}
                        onChange={(e) => setMessageBody(e.target.value)}
                        onKeyDown={onComposerKeyDown}
                        required
                      />
                      <div className="messages-composer__tools">
                        <input className="messages-composer__reply-input" placeholder="Reply ID (optional)" value={replyTo} onChange={(e) => setReplyTo(e.target.value)} />
                        <button
                          type="button"
                          className="messages-link-case-button"
                          onClick={async () => {
                            setShowCasePicker(true);
                            if (!caseSearchRows.length) await searchCases("");
                          }}
                        >
                          <PaperclipIcon />
                          <span>Link Case</span>
                        </button>
                      </div>
                    </div>
                    <button type="submit" className="vilo-btn vilo-btn--primary messages-send-button" disabled={sending || !messageBody.trim()}>
                      <SendIcon />
                      <span>{sending ? "Sending..." : "Send"}</span>
                    </button>
                  </div>
                  {sendError ? <p className="vilo-state vilo-state--error">{sendError}</p> : null}
                </form>
              </>
            )}
          </article>
        </div>
      </div>

      {showCreateModal ? (
        <div className="vilo-modal-overlay" onClick={closeCreateModal}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>New Message</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={closeCreateModal}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <form className="vilo-form-grid" onSubmit={createConversation}>
                {requestedClient ? (
                  <p className="vilo-card-copy">
                    Client context: <strong>{requestedClient.name}</strong>
                    {form.conversation_type === "client" && form.case_id ? "" : " — no linked client conversation could be inferred automatically, so this will open as a regular compose flow unless you choose a case and participant."}
                  </p>
                ) : null}
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
                <button type="submit" className="vilo-btn vilo-btn--primary">Create Conversation</button>
              </form>
            </div>
          </div>
        </div>
      ) : null}

      {showCasePicker ? (
        <div className="vilo-modal-overlay" onClick={() => setShowCasePicker(false)}>
          <div className="vilo-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vilo-modal__header">
              <h3>Link Case</h3>
              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setShowCasePicker(false)}>Close</button>
            </div>
            <div className="vilo-modal__body">
              <div className="vilo-form-grid">
                <label className="messages-search-field">
                  <SearchIcon />
                  <input
                    placeholder="Search case title or number"
                    value={caseSearch}
                    onChange={async (e) => {
                      const next = e.target.value;
                      setCaseSearch(next);
                      await searchCases(next);
                    }}
                  />
                </label>
                <div className="messages-case-search-list">
                  {!caseSearchRows.length ? (
                    <div className="messages-empty-state">
                      <strong>No cases found</strong>
                      <span>No accessible cases matched your search.</span>
                    </div>
                  ) : null}
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
