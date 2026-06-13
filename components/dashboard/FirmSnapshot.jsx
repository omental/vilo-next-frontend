"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
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
                {item.href ? (
                  <Link href={item.href} className="snapshot-stat__link">
                    <div className="snapshot-stat__copy">
                      <p>{item.label}:</p>
                      <strong>{item.value}</strong>
                    </div>
                    <span className={`snapshot-stat__icon ${item.tone}`}>
                      <Icon />
                    </span>
                  </Link>
                ) : (
                  <>
                    <div className="snapshot-stat__copy">
                      <p>{item.label}:</p>
                      <strong>{item.value}</strong>
                    </div>
                    <span className={`snapshot-stat__icon ${item.tone}`}>
                      <Icon />
                    </span>
                  </>
                )}
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
  const safePercent = Number.isFinite(Number(percent)) ? Math.max(0, Math.min(100, Math.round(Number(percent)))) : 0;
  const circumference = 2 * Math.PI * 96;
  const svgSize = 280;
  const center = svgSize / 2;
  const radius = 96;

  return (
    <div className="snapshot-donut" aria-label={`Case Status ${safePercent} percent`}>
      <svg viewBox={`0 0 ${svgSize} ${svgSize}`} aria-hidden="true">
        <circle className="snapshot-donut__track" cx={center} cy={center} r={radius} />
        {segments.map((segment, index) => (
          <motion.circle
            key={segment.key}
            className={`snapshot-donut__segment ${segment.tone}`}
            cx={center}
            cy={center}
            r={radius}
            strokeDasharray={`${segment.length} ${circumference - segment.length}`}
            strokeDashoffset={segment.offset}
            initial={shouldReduceMotion ? false : { opacity: 0, strokeDasharray: `0 ${circumference}` }}
            animate={{ opacity: 1, strokeDasharray: `${segment.length} ${circumference - segment.length}` }}
            transition={{ duration: 0.7, delay: shouldReduceMotion ? 0 : index * 0.12, ease: "easeOut" }}
          />
        ))}
      </svg>

      <div className="snapshot-donut__center">
        <span>Open workload</span>
        <strong>{safePercent}%</strong>
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
  const circumference = 2 * Math.PI * 96;
  let offset = circumference * 0.25;

  return ordered
    .filter((item) => item.value > 0 && total > 0)
    .map((item) => {
      const length = (item.value / total) * circumference;
      const segment = { ...item, length, offset };
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
