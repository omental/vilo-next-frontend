"use client";

import { useMemo, useState } from "react";

const TAB_OPTIONS = ["All Precedents", "Civil Litigation", "Employment Law", "Family Law", "Criminal Law"];
const SORT_OPTIONS = [
  { value: "modified_desc", label: "Last Modified" },
  { value: "modified_asc", label: "Oldest Modified" },
  { value: "title_asc", label: "Title A-Z" },
];

const PRECEDENT_ROWS = [
  {
    id: "will-template",
    title: "Simple will template",
    practiceArea: "Family Law",
    type: "Court Form",
    description: "Estate planning template covering guardianship clauses, residuary gifts, and witness execution prompts.",
    author: "Kevin Brown",
    modifiedAt: "2026-06-13T10:00:00Z",
    tone: "violet",
  },
  {
    id: "petition-support",
    title: "Interim support application",
    practiceArea: "Family Law",
    type: "Motion",
    description: "Short-form application precedent for urgent support relief with affidavit and filing checklist notes.",
    author: "Alicia Wong",
    modifiedAt: "2026-06-11T09:30:00Z",
    tone: "orange",
  },
  {
    id: "employment-warning",
    title: "Workplace investigation notice",
    practiceArea: "Employment Law",
    type: "Letter",
    description: "Employer notice precedent outlining allegation scope, investigator appointment, and response timing.",
    author: "Kevin Brown",
    modifiedAt: "2026-06-12T14:15:00Z",
    tone: "green",
  },
  {
    id: "wrongful-dismissal",
    title: "Wrongful dismissal claim outline",
    practiceArea: "Employment Law",
    type: "Pleading",
    description: "Claim structure covering entitlement, mitigation, bonus treatment, and aggravated damages placeholders.",
    author: "Mia Patel",
    modifiedAt: "2026-06-08T08:45:00Z",
    tone: "blue",
  },
  {
    id: "case-management",
    title: "Case management brief",
    practiceArea: "Civil Litigation",
    type: "Brief",
    description: "Court-ready case conference brief precedent with timetable asks, document disputes, and hearing estimate.",
    author: "Jordan Clark",
    modifiedAt: "2026-06-14T16:20:00Z",
    tone: "red",
  },
  {
    id: "demand-letter",
    title: "Commercial demand letter",
    practiceArea: "Civil Litigation",
    type: "Letter",
    description: "Pre-suit demand letter template with payment demand options, preservation language, and response deadline.",
    author: "Sarah Ali",
    modifiedAt: "2026-06-09T11:10:00Z",
    tone: "violet",
  },
  {
    id: "bail-variation",
    title: "Bail variation request",
    practiceArea: "Criminal Law",
    type: "Application",
    description: "Application precedent for release condition changes with proposed surety and supervision terms.",
    author: "Noah Bennett",
    modifiedAt: "2026-06-10T13:40:00Z",
    tone: "orange",
  },
  {
    id: "plea-brief",
    title: "Sentencing brief starter",
    practiceArea: "Criminal Law",
    type: "Brief",
    description: "Sentencing submission starter including mitigation themes, authorities section, and rehabilitation plan notes.",
    author: "Kevin Brown",
    modifiedAt: "2026-06-07T15:25:00Z",
    tone: "green",
  },
  {
    id: "custody-plan",
    title: "Parenting plan framework",
    practiceArea: "Family Law",
    type: "Agreement",
    description: "Shared parenting framework with holiday schedule, communication protocol, and variation mechanism.",
    author: "Emma Reed",
    modifiedAt: "2026-06-06T12:00:00Z",
    tone: "blue",
  },
];

function formatRelativeDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "recently";

  const diffMs = Date.now() - date.getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  const days = Math.max(0, Math.floor(diffMs / dayMs));

  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;

  const months = Math.floor(days / 30);
  if (months === 1) return "1 month ago";
  return `${months} months ago`;
}

function getTypeOptions(rows) {
  return ["All Types", ...Array.from(new Set(rows.map((row) => row.type))).sort()];
}

function getPracticeAreaOptions(rows) {
  return ["All Practice Areas", ...Array.from(new Set(rows.map((row) => row.practiceArea))).sort()];
}

function compareRows(a, b, sortBy) {
  if (sortBy === "title_asc") return a.title.localeCompare(b.title);
  if (sortBy === "modified_asc") return new Date(a.modifiedAt).getTime() - new Date(b.modifiedAt).getTime();
  return new Date(b.modifiedAt).getTime() - new Date(a.modifiedAt).getTime();
}

function Modal({ title, copy, onClose, children }) {
  return (
    <div className="vilo-modal-overlay" onClick={onClose}>
      <div className="vilo-modal precedents-modal" onClick={(event) => event.stopPropagation()}>
        <div className="vilo-modal__header">
          <div>
            <h3>{title}</h3>
            {copy ? <p className="precedents-modal__copy">{copy}</p> : null}
          </div>
          <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={onClose}>Close</button>
        </div>
        <div className="vilo-modal__body">{children}</div>
      </div>
    </div>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 3.75h6l4.25 4.25V18a2.25 2.25 0 0 1-2.25 2.25h-8A2.25 2.25 0 0 1 5.75 18V6A2.25 2.25 0 0 1 8 3.75Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M14 3.75V8h4.25" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M9 12.25h6M9 15.75h4.25" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
    </svg>
  );
}

function ChipIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="5.5" width="15" height="13" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <path d="M8.5 3.75v3.5M15.5 3.75v3.5M7.75 11.5h8.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

export default function PrecedentsPage() {
  const [activeTab, setActiveTab] = useState(TAB_OPTIONS[0]);
  const [practiceArea, setPracticeArea] = useState("All Practice Areas");
  const [typeFilter, setTypeFilter] = useState("All Types");
  const [sortBy, setSortBy] = useState("modified_desc");
  const [previewItem, setPreviewItem] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);

  const practiceAreaOptions = useMemo(() => getPracticeAreaOptions(PRECEDENT_ROWS), []);
  const typeOptions = useMemo(() => getTypeOptions(PRECEDENT_ROWS), []);

  const filteredRows = useMemo(() => {
    const rows = PRECEDENT_ROWS.filter((row) => {
      if (activeTab !== "All Precedents" && row.practiceArea !== activeTab) return false;
      if (practiceArea !== "All Practice Areas" && row.practiceArea !== practiceArea) return false;
      if (typeFilter !== "All Types" && row.type !== typeFilter) return false;
      return true;
    });

    return [...rows].sort((a, b) => compareRows(a, b, sortBy));
  }, [activeTab, practiceArea, sortBy, typeFilter]);

  return (
    <section className="dashboard-page-stack precedents-page">
      <div className="precedents-page__topbar">
        <div className="dashboard-page-heading precedents-page__heading">
          <h1>Precedents</h1>
          <p>Standardized legal templates and drafting starters for repeatable firm work.</p>
        </div>

        <button type="button" className="vilo-btn vilo-btn--primary precedents-page__create" onClick={() => setCreateOpen(true)}>
          <PlusIcon />
          <span>New Precedent</span>
        </button>
      </div>

      <div className="precedents-shell">
        <div className="precedents-tabs" role="tablist" aria-label="Precedent categories">
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              className={`precedents-tab${activeTab === tab ? " is-active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="precedents-filters">
          <label className="precedents-filter-field">
            <span className="sr-only">Practice area</span>
            <select value={practiceArea} onChange={(event) => setPracticeArea(event.target.value)}>
              {practiceAreaOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
            <ChevronDownIcon />
          </label>

          <label className="precedents-filter-field">
            <span className="sr-only">Type</span>
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
              {typeOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
            <ChevronDownIcon />
          </label>

          <label className="precedents-filter-field">
            <span className="sr-only">Sort order</span>
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              {SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <ChevronDownIcon />
          </label>
        </div>

        <div className="precedents-results-head">
          <h2>{filteredRows.length} {filteredRows.length === 1 ? "Precedent" : "Precedents"}</h2>
        </div>

        {!filteredRows.length ? (
          <div className="vilo-state-block precedents-empty">
            <p className="vilo-state">No precedents matched the selected filters.</p>
            <button
              type="button"
              className="vilo-btn vilo-btn--secondary vilo-btn--xs"
              onClick={() => {
                setActiveTab("All Precedents");
                setPracticeArea("All Practice Areas");
                setTypeFilter("All Types");
                setSortBy("modified_desc");
              }}
            >
              Reset filters
            </button>
          </div>
        ) : (
          <div className="precedents-grid">
            {filteredRows.map((row) => (
              <button
                key={row.id}
                type="button"
                className="precedent-card"
                onClick={() => setPreviewItem(row)}
                aria-label={`Preview ${row.title}`}
              >
                <div className="precedent-card__body">
                  <div className="precedent-card__title-row">
                    <span className="precedent-card__icon">
                      <FileIcon />
                    </span>
                    <div>
                      <h3>{row.title}</h3>
                    </div>
                  </div>

                  <div className={`precedent-card__chip precedent-card__chip--${row.tone}`}>
                    <ChipIcon />
                    <span>{row.practiceArea}</span>
                    <span className="precedent-card__chip-dot" />
                    <span>{row.type}</span>
                  </div>

                  <p>{row.description}</p>
                </div>

                <div className="precedent-card__footer">
                  <span>Modified {formatRelativeDate(row.modifiedAt)}</span>
                  <span className="precedent-card__footer-dot" />
                  <span>by {row.author}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {previewItem ? (
        <Modal
          title={previewItem.title}
          copy="Preview is frontend-only for now. Editing, versioning, and persistence are not configured in this phase."
          onClose={() => setPreviewItem(null)}
        >
          <div className="precedents-modal__stack">
            <div className={`precedent-card__chip precedent-card__chip--${previewItem.tone}`}>
              <ChipIcon />
              <span>{previewItem.practiceArea}</span>
              <span className="precedent-card__chip-dot" />
              <span>{previewItem.type}</span>
            </div>
            <p className="precedents-modal__description">{previewItem.description}</p>
            <div className="precedents-modal__meta">
              <span>Modified {formatRelativeDate(previewItem.modifiedAt)}</span>
              <span>Author: {previewItem.author}</span>
            </div>
          </div>
        </Modal>
      ) : null}

      {createOpen ? (
        <Modal
          title="New precedent"
          copy="Precedent creation is not configured in the current app yet. This placeholder preserves the route and avoids implying saved data."
          onClose={() => setCreateOpen(false)}
        >
          <div className="precedents-modal__stack">
            <p className="precedents-modal__description">
              Wire this action to an existing create flow or precedent API once the backend model and permissions are available.
            </p>
            <div className="precedents-modal__actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => setCreateOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}
