"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const STATUS_OPTIONS = ["not_started", "in_progress", "waiting", "completed"];
const PRIORITY_OPTIONS = ["low", "medium", "high", "urgent"];
const TASK_TYPE_OPTIONS = ["general", "deadline", "court", "client_follow_up", "document", "billing", "other"];

const initialForm = {
  client_id: "",
  case_id: "",
  assigned_to: "",
  title: "",
  description: "",
  task_type: "general",
  status: "not_started",
  priority: "medium",
  due_date: "",
  reminder_at: "",
  notes: "",
};

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatDateOnly(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  const localDate = new Date(date.getTime() - offset * 60000);
  return localDate.toISOString().slice(0, 16);
}

function normalizeLabel(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function isCompleted(task) {
  return task?.status === "completed";
}

function isOverdue(task) {
  return Boolean(task?.is_overdue);
}

export default function TasksPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading tasks...</p></div></section>}>
      <TasksPageContent />
    </Suspense>
  );
}

function TasksPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const titleInputRef = useRef(null);
  const formCardRef = useRef(null);
  const highlightedTaskRef = useRef(null);

  const [tasks, setTasks] = useState([]);
  const [cases, setCases] = useState([]);
  const [clients, setClients] = useState([]);
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [createOpen, setCreateOpen] = useState(searchParams.get("create") === "1");
  const [menuOpenId, setMenuOpenId] = useState(null);

  const requestedClientId = Number(searchParams.get("client_id") || 0);
  const requestedCaseId = Number(searchParams.get("case_id") || 0);
  const requestedTaskId = Number(searchParams.get("task_id") || 0);
  const requestedDueDate = searchParams.get("due_date") || "";
  const requestedFilter = searchParams.get("filter") || "";

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [taskData, caseData, clientData, teamData] = await Promise.all([
        apiRequest("/api/v1/tasks?include_archived=false"),
        apiRequest("/api/v1/cases"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/team"),
      ]);
      setTasks(taskData || []);
      setCases(caseData || []);
      setClients(clientData || []);
      setTeam((teamData || []).filter((user) => user.role !== "client"));
    } catch (err) {
      setError(err.message || "Unable to load tasks.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const casesById = useMemo(
    () => new Map(cases.map((row) => [Number(row.id), row])),
    [cases],
  );

  const clientsById = useMemo(
    () => new Map(clients.map((row) => [Number(row.id), row])),
    [clients],
  );

  const teamById = useMemo(
    () => new Map(team.map((row) => [Number(row.id), row])),
    [team],
  );

  const selectedTask = useMemo(
    () => tasks.find((task) => Number(task.id) === requestedTaskId) || null,
    [requestedTaskId, tasks],
  );

  useEffect(() => {
    const shouldOpen = searchParams.get("create") === "1";
    setCreateOpen(shouldOpen);
    if (!shouldOpen) return;

    const requestedCase = requestedCaseId ? casesById.get(requestedCaseId) : null;
    const derivedClientId = requestedCase ? Number(requestedCase.client_id || 0) : requestedClientId;

    setForm((current) => ({
      ...current,
      client_id: derivedClientId ? String(derivedClientId) : current.client_id,
      case_id: requestedCaseId ? String(requestedCaseId) : current.case_id,
      due_date: requestedDueDate && !current.due_date ? `${requestedDueDate}T09:00` : current.due_date,
    }));

    formCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    titleInputRef.current?.focus();
  }, [casesById, requestedCaseId, requestedClientId, requestedDueDate, searchParams]);

  const selectedClientId = Number(form.client_id || 0);

  const availableCases = useMemo(() => {
    if (!selectedClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === selectedClientId);
  }, [cases, selectedClientId]);

  useEffect(() => {
    if (!form.case_id) return;
    const linkedCase = casesById.get(Number(form.case_id));
    if (!linkedCase) return;
    const nextClientId = String(linkedCase.client_id || "");
    if (nextClientId && nextClientId !== form.client_id) {
      setForm((current) => ({ ...current, client_id: nextClientId }));
    }
  }, [casesById, form.case_id, form.client_id]);

  const filteredTasks = useMemo(() => {
    const now = new Date();
    let nextTasks = tasks;

    if (requestedFilter === "due_today") {
      nextTasks = nextTasks.filter((task) => {
        if (!task.due_date || isCompleted(task)) return false;
        return new Date(task.due_date).toDateString() === now.toDateString();
      });
    } else if (requestedFilter === "overdue") {
      nextTasks = nextTasks.filter((task) => {
        if (!task.due_date || isCompleted(task)) return false;
        return new Date(task.due_date) < now;
      });
    }

    if (requestedTaskId && !nextTasks.some((task) => Number(task.id) === requestedTaskId) && selectedTask) {
      nextTasks = [selectedTask, ...nextTasks];
    }

    return nextTasks;
  }, [requestedFilter, requestedTaskId, selectedTask, tasks]);

  useEffect(() => {
    if (!requestedTaskId || !filteredTasks.some((task) => Number(task.id) === requestedTaskId)) return;
    highlightedTaskRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [filteredTasks, requestedTaskId]);

  function updateQuery(nextParams) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(nextParams).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") params.delete(key);
      else params.set(key, String(value));
    });
    const next = params.toString();
    router.push(next ? `/dashboard/tasks?${next}` : "/dashboard/tasks");
  }

  function handleOpenCreate() {
    updateQuery({ create: "1" });
  }

  function handleCloseCreate() {
    setCreateOpen(false);
    setForm(initialForm);
    updateQuery({ create: null, client_id: requestedTaskId ? null : searchParams.get("client_id"), case_id: null, due_date: null });
  }

  function focusTask(taskId) {
    updateQuery({ task_id: taskId });
  }

  async function createTask(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      await apiRequest("/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: form.title,
          description: form.description || null,
          client_id: form.client_id ? Number(form.client_id) : null,
          case_id: form.case_id ? Number(form.case_id) : null,
          assigned_user_id: form.assigned_to ? Number(form.assigned_to) : null,
          task_type: form.task_type,
          status: form.status,
          priority: form.priority,
          due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
          reminder_at: form.reminder_at ? new Date(form.reminder_at).toISOString() : null,
          notes: form.notes || null,
        }),
      });

      setSuccess("Task created successfully.");
      setForm(initialForm);
      updateQuery({ create: null, task_id: null });
      setCreateOpen(false);
      await load();
    } catch (err) {
      setError(err.message || "Unable to create task.");
    } finally {
      setSubmitting(false);
    }
  }

  async function completeTask(taskId) {
    setError("");
    await apiRequest(`/api/v1/tasks/${taskId}/complete`, { method: "POST" });
    setMenuOpenId(null);
    await load();
  }

  async function archiveTask(taskId) {
    setError("");
    await apiRequest(`/api/v1/tasks/${taskId}/archive`, { method: "POST" });
    setMenuOpenId(null);
    if (requestedTaskId === Number(taskId)) updateQuery({ task_id: null });
    await load();
  }

  const requestedClient = requestedClientId ? clientsById.get(requestedClientId) : null;
  const requestedCase = requestedCaseId ? casesById.get(requestedCaseId) : null;

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading dashboard-page-heading--split">
        <div>
          <h1>Tasks</h1>
          <p className="vilo-card-copy">
            {requestedFilter === "due_today" ? "Tasks due today." : requestedFilter === "overdue" ? "Tasks that need immediate attention." : "Manage internal work, deadlines, and follow-ups."}
          </p>
        </div>
        <button type="button" className="vilo-btn vilo-btn--primary" onClick={handleOpenCreate}>Create Task</button>
      </div>

      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}
      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}

      <div className="tasks-page-grid">
        <div className="tasks-page-main">
          <article ref={formCardRef} className="dashboard-card vilo-form-card vilo-collapsible-card">
            <div className="dashboard-card__header dashboard-card__header--action">
              <div>
                <h2>Create Task</h2>
                <p className="vilo-card-copy">
                  {requestedCase ? `Case context: ${requestedCase.title}` : requestedClient ? `Client context: ${requestedClient.name}` : "Start with a title, assignee, status, priority, and due date."}
                </p>
              </div>
              <button
                type="button"
                className={createOpen ? "vilo-btn vilo-btn--secondary vilo-btn--xs" : "vilo-btn vilo-btn--primary vilo-btn--xs"}
                aria-expanded={createOpen}
                onClick={() => {
                  if (createOpen) handleCloseCreate();
                  else handleOpenCreate();
                }}
              >
                {createOpen ? "Hide Form" : "Open Form"}
              </button>
            </div>

            {createOpen ? (
              <form className="vilo-form-grid vilo-collapsible-card__body" onSubmit={createTask}>
                <input
                  ref={titleInputRef}
                  placeholder="Task title"
                  value={form.title}
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  required
                />
                <textarea
                  placeholder="Description"
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                />

                <div className="vilo-form-row-two">
                  <select
                    value={form.client_id}
                    onChange={(event) => setForm((current) => ({ ...current, client_id: event.target.value, case_id: "" }))}
                  >
                    <option value="">Select client</option>
                    {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                  <select
                    value={form.case_id}
                    onChange={(event) => setForm((current) => ({ ...current, case_id: event.target.value }))}
                  >
                    <option value="">No linked case</option>
                    {availableCases.map((caseRow) => <option key={caseRow.id} value={caseRow.id}>{caseRow.title}</option>)}
                  </select>
                </div>

                <div className="vilo-form-row-two">
                  <select
                    value={form.assigned_to}
                    onChange={(event) => setForm((current) => ({ ...current, assigned_to: event.target.value }))}
                    required
                  >
                    <option value="">Assigned user</option>
                    {team.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.role})</option>)}
                  </select>
                  <select
                    value={form.task_type}
                    onChange={(event) => setForm((current) => ({ ...current, task_type: event.target.value }))}
                  >
                    {TASK_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{normalizeLabel(option)}</option>)}
                  </select>
                </div>

                <div className="vilo-form-row-two">
                  <select
                    value={form.status}
                    onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
                  >
                    {STATUS_OPTIONS.map((option) => <option key={option} value={option}>{normalizeLabel(option)}</option>)}
                  </select>
                  <select
                    value={form.priority}
                    onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value }))}
                  >
                    {PRIORITY_OPTIONS.map((option) => <option key={option} value={option}>{normalizeLabel(option)}</option>)}
                  </select>
                </div>

                <div className="vilo-form-row-two">
                  <input
                    type="datetime-local"
                    value={form.due_date}
                    onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))}
                    required
                  />
                  <input
                    type="datetime-local"
                    value={form.reminder_at}
                    onChange={(event) => setForm((current) => ({ ...current, reminder_at: event.target.value }))}
                  />
                </div>

                <textarea
                  placeholder="Internal notes"
                  value={form.notes}
                  onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                />

                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={handleCloseCreate}>Cancel</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={submitting}>
                    {submitting ? "Creating..." : "Create Task"}
                  </button>
                </div>
              </form>
            ) : null}
          </article>

          <article className="dashboard-card vilo-table-card">
            <div className="dashboard-card__header"><h2>{requestedFilter === "due_today" ? "Tasks Due Today" : requestedFilter === "overdue" ? "Overdue Tasks" : "Task List"}</h2></div>
            {loading ? <p className="vilo-state">Loading tasks...</p> : null}
            {!loading && !filteredTasks.length ? <p className="vilo-state">No tasks matched this view.</p> : null}
            {!loading && filteredTasks.length ? (
              <div className={`vilo-table-wrap case-table-wrap${menuOpenId ? " case-table-wrap--menu-visible" : ""}`}>
                <table className="team-table">
                  <thead>
                    <tr><th>Title</th><th>Context</th><th>Status</th><th>Priority</th><th>Due</th><th>Action</th></tr>
                  </thead>
                  <tbody>
                    {filteredTasks.map((task) => {
                      const linkedCase = task.case_id ? casesById.get(Number(task.case_id)) : null;
                      const linkedClient = task.client_id ? clientsById.get(Number(task.client_id)) : null;
                      const isSelected = Number(task.id) === requestedTaskId;
                      return (
                        <tr
                          key={task.id}
                          ref={isSelected ? highlightedTaskRef : null}
                          className={`tasks-table-row${isSelected ? " team-table__row-highlight" : ""}${isCompleted(task) ? " is-completed" : ""}${isOverdue(task) ? " is-overdue" : ""}`}
                          onClick={() => focusTask(task.id)}
                        >
                          <td>
                            <div className="tasks-table-title">
                              <strong>{task.title}</strong>
                              <span>{normalizeLabel(task.task_type || "general")}</span>
                            </div>
                          </td>
                          <td>
                            <div className="tasks-table-context">
                              <span>{linkedClient?.name || "No client linked"}</span>
                              <small>{linkedCase ? linkedCase.title : "No case linked"}</small>
                            </div>
                          </td>
                          <td>
                            <div className="tasks-status-stack">
                              <span className={`vilo-badge vilo-badge--${task.status}`}>{normalizeLabel(task.status)}</span>
                              {task.is_overdue ? <span className="vilo-badge vilo-badge--overdue">Overdue</span> : null}
                            </div>
                          </td>
                          <td><span className={`vilo-badge vilo-badge--priority-${task.priority}`}>{normalizeLabel(task.priority)}</span></td>
                          <td>{formatDateTime(task.due_date)}</td>
                          <td onClick={(event) => event.stopPropagation()}>
                            <div className="vilo-table-actions case-row-actions">
                              <button
                                type="button"
                                className="vilo-btn vilo-btn--ghost vilo-btn--xs task-action-trigger"
                                aria-expanded={menuOpenId === task.id}
                                onClick={() => setMenuOpenId((openId) => (openId === task.id ? null : task.id))}
                              >
                                Actions
                              </button>
                              {menuOpenId === task.id ? (
                                <div className="case-actions-menu task-actions-menu">
                                  <button type="button" onClick={() => focusTask(task.id)}>View details</button>
                                  {task.case_id ? <Link href={`/dashboard/cases/${task.case_id}`}>View case</Link> : null}
                                  {task.client_id ? <Link href={`/dashboard/clients/${task.client_id}`}>View client</Link> : null}
                                  {!isCompleted(task) ? <button type="button" onClick={() => completeTask(task.id)}>Complete task</button> : null}
                                  <button type="button" onClick={() => archiveTask(task.id)}>Archive task</button>
                                </div>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </article>
        </div>

        <aside className="tasks-page-side">
          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Task Detail</h2></div>
            {selectedTask ? (
              <div className={`task-detail-card${isCompleted(selectedTask) ? " is-completed" : ""}${isOverdue(selectedTask) ? " is-overdue" : ""}`}>
                <div className="task-detail-card__header">
                  <div>
                    <strong>{selectedTask.title}</strong>
                    <p>{selectedTask.description || "No description provided."}</p>
                  </div>
                  <div className="task-detail-card__badges">
                    <span className={`vilo-badge vilo-badge--${selectedTask.status}`}>{normalizeLabel(selectedTask.status)}</span>
                    <span className={`vilo-badge vilo-badge--priority-${selectedTask.priority}`}>{normalizeLabel(selectedTask.priority)}</span>
                    {selectedTask.is_overdue ? <span className="vilo-badge vilo-badge--overdue">Overdue</span> : null}
                  </div>
                </div>

                <div className="task-detail-grid">
                  <div><span>Task type</span><strong>{normalizeLabel(selectedTask.task_type || "general")}</strong></div>
                  <div><span>Assigned user</span><strong>{teamById.get(Number(selectedTask.assigned_user_id || selectedTask.assigned_to || 0))?.name || "Unassigned"}</strong></div>
                  <div><span>Due date</span><strong>{formatDateTime(selectedTask.due_date)}</strong></div>
                  <div><span>Reminder</span><strong>{formatDateTime(selectedTask.reminder_at)}</strong></div>
                  <div><span>Client</span><strong>{clientsById.get(Number(selectedTask.client_id || 0))?.name || "No client linked"}</strong></div>
                  <div><span>Case</span><strong>{casesById.get(Number(selectedTask.case_id || 0))?.title || "No case linked"}</strong></div>
                </div>

                <div className="task-detail-notes">
                  <span>Notes</span>
                  <p>{selectedTask.notes || "No internal notes."}</p>
                </div>

                <div className="vilo-table-actions">
                  {selectedTask.case_id ? <Link className="vilo-btn vilo-btn--secondary vilo-btn--xs" href={`/dashboard/cases/${selectedTask.case_id}`}>Open Case</Link> : null}
                  {selectedTask.client_id ? <Link className="vilo-btn vilo-btn--secondary vilo-btn--xs" href={`/dashboard/clients/${selectedTask.client_id}`}>Open Client</Link> : null}
                  {!isCompleted(selectedTask) ? <button type="button" className="vilo-btn vilo-btn--primary vilo-btn--xs" onClick={() => completeTask(selectedTask.id)}>Mark Complete</button> : null}
                </div>
              </div>
            ) : (
              <p className="vilo-card-copy">Select a task to view its full details, notes, due date, and related case or client.</p>
            )}
          </article>

          <article className="dashboard-card">
            <div className="dashboard-card__header"><h2>Current Context</h2></div>
            <div className="task-context-stack">
              <div className="task-context-row">
                <span>Client route context</span>
                <strong>{requestedClient?.name || "None"}</strong>
              </div>
              <div className="task-context-row">
                <span>Case route context</span>
                <strong>{requestedCase?.title || "None"}</strong>
              </div>
              <div className="task-context-row">
                <span>Prefilled due date</span>
                <strong>{requestedDueDate ? formatDateOnly(requestedDueDate) : "None"}</strong>
              </div>
            </div>
          </article>
        </aside>
      </div>
    </section>
  );
}
