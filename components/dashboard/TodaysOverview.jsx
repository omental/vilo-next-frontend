"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { createCardVariants, createHoverLift, createItemVariants } from "../motion";

const fallbackStatItems = [
  { label: "Due Today", value: 12 },
  { label: "Overdue", value: 4 },
  { label: "Messages", value: 9 }
];

const fallbackTimelineRows = [
  { label: "JMMB Bank - 103XXX", priority: "High", tone: "is-high" },
  { label: "JMMB Bank - 103XXX", priority: "Low", tone: "is-low" },
  { label: "JMMB Bank - 103XXX", priority: "Normal", tone: "is-normal" }
];

export function TodaysOverview({ stats = fallbackStatItems, timelineRows = fallbackTimelineRows }) {
  const shouldReduceMotion = useReducedMotion();
  const cardVariants = createCardVariants(shouldReduceMotion);
  const itemVariants = createItemVariants(shouldReduceMotion, "y", 10);
  const hoverLift = createHoverLift(shouldReduceMotion);

  return (
    <motion.section
      className="dashboard-card dashboard-card--overview"
      aria-labelledby="todays-overview-title"
      variants={cardVariants}
      whileHover={hoverLift}
    >
      <div className="dashboard-card__header">
        <h2 id="todays-overview-title">Today&apos;s Overview</h2>
      </div>

      <div className="overview-stats">
        {stats.map((item) => (
          <motion.article key={item.label} variants={itemVariants}>
            {item.href ? (
              <Link href={item.href} className="overview-stat overview-stat--link">
                <p>{item.label}</p>
                <strong>{item.value}</strong>
              </Link>
            ) : (
              <div className="overview-stat">
                <p>{item.label}</p>
                <strong>{item.value}</strong>
              </div>
            )}
          </motion.article>
        ))}
      </div>

      <div className="overview-table-block">
        <h3>Priority Timeline</h3>

        <div className="overview-table-wrap">
          <table className="overview-table">
            <thead>
              <tr>
                <th>Timeline</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              {timelineRows.map((row, index) => (
                <motion.tr key={`${row.priority}-${index}`} variants={itemVariants}>
                  <td>
                    {row.href ? (
                      <Link className="overview-table__link" href={row.href}>{row.label}</Link>
                    ) : (
                      row.label
                    )}
                  </td>
                  <td>
                    <motion.span
                      className={`priority-badge ${row.tone}`}
                      initial={shouldReduceMotion ? false : { scale: 0.9, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ duration: 0.28, delay: shouldReduceMotion ? 0 : index * 0.08 }}
                    >
                      {row.priority}
                    </motion.span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.section>
  );
}
