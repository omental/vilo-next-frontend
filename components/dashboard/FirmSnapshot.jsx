"use client";

import { motion, useReducedMotion } from "framer-motion";
import { createCardVariants, createHoverLift, createItemVariants } from "../motion";

const snapshotStats = [
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

export function FirmSnapshot() {
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
          <SnapshotDonut />

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
            const Icon = item.icon;

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

function SnapshotDonut() {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="snapshot-donut" aria-label="Case Status 72 percent">
      <svg viewBox="0 0 240 240" aria-hidden="true">
        <circle className="snapshot-donut__track" cx="120" cy="120" r="78" />
        <motion.circle
          className="snapshot-donut__segment is-active"
          cx="120"
          cy="120"
          r="78"
          pathLength="100"
          strokeDasharray="50 50"
          initial={shouldReduceMotion ? false : { strokeDashoffset: 100 }}
          animate={{ strokeDashoffset: 11 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
        <motion.circle
          className="snapshot-donut__segment is-court"
          cx="120"
          cy="120"
          r="78"
          pathLength="100"
          strokeDasharray="8 92"
          initial={shouldReduceMotion ? false : { strokeDashoffset: 100 }}
          animate={{ strokeDashoffset: -39 }}
          transition={{ duration: 0.8, delay: 0.08, ease: "easeOut" }}
        />
        <motion.circle
          className="snapshot-donut__segment is-pending"
          cx="120"
          cy="120"
          r="78"
          pathLength="100"
          strokeDasharray="17 83"
          initial={shouldReduceMotion ? false : { strokeDashoffset: 100 }}
          animate={{ strokeDashoffset: -49 }}
          transition={{ duration: 0.8, delay: 0.16, ease: "easeOut" }}
        />
      </svg>

      <div className="snapshot-donut__center">
        <span>Case Status</span>
        <strong>72%</strong>
      </div>
    </div>
  );
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
