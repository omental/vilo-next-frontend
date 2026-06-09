"use client";

import { motion, useReducedMotion } from "framer-motion";
import { createCardVariants, createHoverLift, createItemVariants } from "../motion";

const fallbackSnapshotStats = [
  {
    label: "Total Files",
    value: 100,
    tone: "is-violet",
    icon: StackIcon
  },
  {
    label: "High Priority",
    value: 15,
    tone: "is-orange",
    icon: BriefcaseIcon
  },
  {
    label: "Tasks",
    value: 88,
    tone: "is-green",
    icon: CheckCircleIcon
  },
  {
    label: "Stalled Files",
    value: 10,
    tone: "is-red",
    icon: AlertTriangleIcon
  }
];

const legendItems = [
  { label: "Active", tone: "is-active" },
  { label: "Court", tone: "is-court" },
  { label: "Closed", tone: "is-closed" },
  { label: "Pending", tone: "is-pending" }
];

export function FirmSnapshot({
  snapshotStats = fallbackSnapshotStats,
  caseStatusPercent = 72,
  caseStatusCounts = { active: 0, court: 0, closed: 0, pending: 0 },
}) {
  const shouldReduceMotion = useReducedMotion();
  const cardVariants = createCardVariants(shouldReduceMotion);
  const itemVariants = createItemVariants(shouldReduceMotion, "y", 10);
  const hoverLift = createHoverLift(shouldReduceMotion);

  return (
    <motion.section
      className="dashboard-card dashboard-card--snapshot"
      aria-labelledby="firm-snapshot-title"
      variants={cardVariants}
      whileHover={hoverLift}
    >
      <div className="dashboard-card__header">
        <h2 id="firm-snapshot-title">Firm Snapshot</h2>
      </div>

      <div className="snapshot-layout">
        <div className="snapshot-chart-block">
          <p className="snapshot-chart-block__label">Case Status</p>
          <SnapshotDonut percent={caseStatusPercent} counts={caseStatusCounts} />

          <ul className="snapshot-legend" aria-label="Firm snapshot legend">
            {legendItems.map((item) => (
              <li key={item.label}>
                <span className={`snapshot-legend__dot ${item.tone}`} />
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="snapshot-stats">
          {snapshotStats.map((item) => {
            const Icon = item.icon || StackIcon;

            return (
              <motion.article key={item.label} className="snapshot-stat" variants={itemVariants}>
                <div className="snapshot-stat__copy">
                  <p>{item.label}:</p>
                  <strong>{item.value}</strong>
                </div>
                <span className={`snapshot-stat__icon ${item.tone}`}>
                  <Icon />
                </span>
              </motion.article>
            );
          })}
        </div>
      </div>
    </motion.section>
  );
}

function SnapshotDonut({ percent = 72, counts = { active: 0, court: 0, closed: 0, pending: 0 } }) {
  const shouldReduceMotion = useReducedMotion();
  const segments = buildSegments(counts);

  return (
    <div className="snapshot-donut" aria-label={`Case Status ${percent} percent`}>
      <svg viewBox="0 0 280 280" aria-hidden="true">
        <circle className="snapshot-donut__track" cx="140" cy="140" r="96" />
        {segments.map((segment, index) => (
          <motion.circle
            key={segment.key}
            className={`snapshot-donut__segment ${segment.tone}`}
            cx="140"
            cy="140"
            r="96"
            pathLength="100"
            strokeDasharray={`${segment.length} ${100 - segment.length}`}
            strokeDashoffset={segment.offset}
            initial={shouldReduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: shouldReduceMotion ? 0 : index * 0.08, ease: "easeOut" }}
          />
        ))}
      </svg>

      <div className="snapshot-donut__center">
        <strong>{percent}%</strong>
      </div>
    </div>
  );
}

function buildSegments(counts) {
  const ordered = [
    { key: "active", tone: "is-active", value: Number(counts.active || 0) },
    { key: "court", tone: "is-court", value: Number(counts.court || 0) },
    { key: "closed", tone: "is-closed", value: Number(counts.closed || 0) },
    { key: "pending", tone: "is-pending", value: Number(counts.pending || 0) },
  ];
  const total = ordered.reduce((sum, item) => sum + item.value, 0);
  let offset = 25;

  return ordered
    .filter((item) => item.value > 0 && total > 0)
    .map((item) => {
      const length = Math.max(4, (item.value / total) * 100);
      const segment = { ...item, length: Math.min(length, 100), offset };
      offset -= segment.length;
      return segment;
    });
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

function StackIcon() {
  return (
    <IconBase>
      <path d="m12 4 7 3.5-7 3.5-7-3.5L12 4Z" />
      <path d="m5 12 7 3.5 7-3.5" />
      <path d="m5 16.5 7 3.5 7-3.5" />
    </IconBase>
  );
}

function BriefcaseIcon() {
  return (
    <IconBase>
      <rect x="3" y="7" width="18" height="13" rx="3" />
      <path d="M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7" />
    </IconBase>
  );
}

function CheckCircleIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.4 12.2 2.3 2.4 4.9-5.1" />
    </IconBase>
  );
}

function AlertTriangleIcon() {
  return (
    <IconBase>
      <path d="M12 4.5 20 18a2 2 0 0 1-1.72 3H5.72A2 2 0 0 1 4 18L12 4.5Z" />
      <path d="M12 9v4.5" />
      <path d="M12 17h.01" />
    </IconBase>
  );
}
