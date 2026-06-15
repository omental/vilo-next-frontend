"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiRequest } from "../../../lib/api";

const initialForm = {
  case_id: "",
  assigned_to: "",
  title: "",
  description: "",
  status: "pending",
  priority: "medium",
  due_date: "",
};

export default function TasksPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading tasks...</p></div></section>}>
      <TasksPageContent />
    </Suspense>
  );
}

function TasksPageContent() {
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
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [createOpen, setCreateOpen] = useState(searchParams.get("create") === "1");
  const [menuOpenId, setMenuOpenId] = useState(null);
  const requestedClientId = Number(searchParams.get("client_id") || 0);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [taskData, caseData, clientData, teamData] = await Promise.all([
        apiRequest("/api/v1/tasks"),
        apiRequest("/api/v1/cases"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/team"),
      ]);
      setTasks(taskData);
      setCases(caseData);
      setClients(clientData);
      setTeam(teamData.filter((u) => u.role !== "client"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const shouldOpen = searchParams.get("create") === "1";
    setCreateOpen(shouldOpen);
    if (!shouldOpen) return;
    const requestedCases = requestedClientId
      ? cases.filter((row) => Number(row.client_id) === requestedClientId)
      : [];
    setForm((current) => {
      const nextCaseId = current.case_id || (requestedCases.length === 1 ? String(requestedCases[0].id) : "");
      return { ...current, case_id: nextCaseId };
    });
    formCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    titleInputRef.current?.focus();
  }, [cases, requestedClientId, searchParams]);

  const requestedClient = useMemo(
    () => clients.find((client) => Number(client.id) === requestedClientId) || null,
    [clients, requestedClientId],
  );

  const caseOptions = useMemo(() => {
    if (!requestedClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === requestedClientId);
  }, [cases, requestedClientId]);

  const filteredTasks = useMemo(() => {
    const filter = searchParams.get("filter");
    const selectedTaskId = Number(searchParams.get("task_id") || 0);
    const now = new Date();
    let nextTasks = tasks;
    if (filter === "due_today") {
      nextTasks = tasks.filter((task) => {
        if (!task.due_date || task.status === "completed") return false;
        const due = new Date(task.due_date);
        return due.toDateString() === now.toDateString();
      });
    }
    if (filter === "overdue") {
      nextTasks = tasks.filter((task) => {
        if (!task.due_date || task.status === "completed") return false;
        return new Date(task.due_date) < now;
      });
    }
    if (selectedTaskId && !nextTasks.some((task) => Number(task.id) === selectedTaskId)) {
      const selectedTask = tasks.find((task) => Number(task.id) === selectedTaskId);
      if (selectedTask) {
        nextTasks = [selectedTask, ...nextTasks];
      }
    }
    return nextTasks;
  }, [searchParams, tasks]);

  const selectedTaskId = Number(searchParams.get("task_id") || 0);

  useEffect(() => {
    if (!selectedTaskId || !filteredTasks.some((task) => Number(task.id) === selectedTaskId)) return;
    highlightedTaskRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [filteredTasks, selectedTaskId]);

  async function createTask(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await apiRequest("/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          case_id: form.case_id ? Number(form.case_id) : null,
          assigned_to: form.assigned_to ? Number(form.assigned_to) : null,
          due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        }),
      });
      setForm(initialForm);
      setCreateOpen(false);
      setSuccess("Task created successfully.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function completeTask(taskId) {
    await apiRequest(`/api/v1/tasks/${taskId}/complete`, { method: "PATCH" });
    setMenuOpenId(null);
    await load();
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Tasks</h1></div>

      {success ? <div className="vilo-state-block"><p className="vilo-state">{success}</p></div> : null}

      <article ref={formCardRef} className="dashboard-card vilo-form-card vilo-collapsible-card">
        <div className="dashboard-card__header dashboard-card__header--action">
          <h2>Create Task</h2>
          <button
            type="button"
            className={createOpen ? "vilo-btn vilo-btn--secondary vilo-btn--xs" : "vilo-btn vilo-btn--primary vilo-btn--xs"}
            aria-expanded={createOpen}
            onClick={() => {
              setCreateOpen((open) => !open);
              setSuccess("");
            }}
          >
            {createOpen ? "Hide Form" : "Create Task"}
          </button>
        </div>
        {createOpen ? (
          <form className="vilo-form-grid vilo-collapsible-card__body" onSubmit={createTask}>
            <input ref={titleInputRef} placeholder="Task title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

            <div className="vilo-form-row-two">
              <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
                <option value="">No linked case</option>
                {caseOptions.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
              <select value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}>
                <option value="">Unassigned</option>
                {team.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}
              </select>
            </div>

            {requestedClient ? (
              <p className="vilo-card-copy">
                Client context: <strong>{requestedClient.name}</strong>
                {caseOptions.length ? "" : " — tasks can only link to cases, and this client has no available cases yet."}
              </p>
            ) : null}

            <div className="vilo-form-row-two">
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="pending">pending</option>
                <option value="in_progress">in_progress</option>
                <option value="completed">completed</option>
                <option value="cancelled">cancelled</option>
              </select>
              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="urgent">urgent</option>
              </select>
            </div>

            <input type="datetime-local" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            <button type="submit">Create Task</button>
          </form>
        ) : null}
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>{searchParams.get("filter") === "due_today" ? "Tasks Due Today" : searchParams.get("filter") === "overdue" ? "Overdue Tasks" : "Task List"}</h2></div>
        {loading ? <p className="vilo-state">Loading tasks...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error && filteredTasks.length === 0 ? <p className="vilo-state">No tasks matched this view.</p> : null}
        {!loading && !error && filteredTasks.length > 0 ? (
          <div className={`vilo-table-wrap case-table-wrap${menuOpenId ? " case-table-wrap--menu-visible" : ""}`}>
            <table className="team-table">
              <thead><tr><th>Title</th><th>Status</th><th>Priority</th><th>Due</th><th>Action</th></tr></thead>
              <tbody>
                {filteredTasks.map((task) => (
                  <tr
                    key={task.id}
                    ref={Number(task.id) === selectedTaskId ? highlightedTaskRef : null}
                    className={Number(task.id) === selectedTaskId ? "team-table__row-highlight" : ""}
                  >
                    <td>{task.title}</td>
                    <td><span className={`vilo-badge vilo-badge--${task.status}`}>{task.status}</span></td>
                    <td><span className={`vilo-badge vilo-badge--priority-${task.priority}`}>{task.priority}</span></td>
                    <td>{task.due_date ? new Date(task.due_date).toLocaleString() : "-"}</td>
                    <td>
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
                            {task.case_id ? <Link href={`/dashboard/cases/${task.case_id}`}>View case</Link> : null}
                            {task.status !== "completed" ? (
                              <button type="button" onClick={() => completeTask(task.id)}>Complete task</button>
                            ) : (
                              <button type="button" disabled>Completed</button>
                            )}
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
