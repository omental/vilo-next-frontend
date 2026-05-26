"use client";

import { useEffect, useState } from "react";
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
  const [tasks, setTasks] = useState([]);
  const [cases, setCases] = useState([]);
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [taskData, caseData, teamData] = await Promise.all([
        apiRequest("/api/v1/tasks"),
        apiRequest("/api/v1/cases"),
        apiRequest("/api/v1/team"),
      ]);
      setTasks(taskData);
      setCases(caseData);
      setTeam(teamData.filter((u) => u.role !== "client"));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createTask(e) {
    e.preventDefault();
    setError("");
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
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function completeTask(taskId) {
    await apiRequest(`/api/v1/tasks/${taskId}/complete`, { method: "PATCH" });
    await load();
  }

  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading"><h1>Tasks</h1></div>

      <article className="dashboard-card vilo-form-card">
        <div className="dashboard-card__header"><h2>Create Task</h2></div>
        <form className="vilo-form-grid" onSubmit={createTask}>
          <input placeholder="Task title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          <div className="vilo-form-row-two">
            <select value={form.case_id} onChange={(e) => setForm({ ...form, case_id: e.target.value })}>
              <option value="">No linked case</option>
              {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
            <select value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}>
              <option value="">Unassigned</option>
              {team.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}
            </select>
          </div>

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
      </article>

      <article className="dashboard-card vilo-table-card">
        <div className="dashboard-card__header"><h2>Task List</h2></div>
        {loading ? <p className="vilo-state">Loading tasks...</p> : null}
        {error ? <p className="vilo-state vilo-state--error">{error}</p> : null}
        {!loading && !error ? (
          <div className="vilo-table-wrap">
            <table className="team-table">
              <thead><tr><th>Title</th><th>Status</th><th>Priority</th><th>Due</th><th>Action</th></tr></thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td>{task.title}</td>
                    <td><span className={`vilo-badge vilo-badge--${task.status}`}>{task.status}</span></td>
                    <td><span className={`vilo-badge vilo-badge--priority-${task.priority}`}>{task.priority}</span></td>
                    <td>{task.due_date ? new Date(task.due_date).toLocaleString() : "-"}</td>
                    <td>{task.status !== "completed" ? <button onClick={() => completeTask(task.id)}>Complete</button> : "Done"}</td>
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
