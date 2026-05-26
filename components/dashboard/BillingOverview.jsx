"use client";

import { motion, useReducedMotion } from "framer-motion";
import { createCardVariants, createHoverLift, createItemVariants } from "../motion";

const fallbackBillingBars = [
  { label: "Paid", value: 210, tone: "is-paid" },
  { label: "Unpaid", value: 130, tone: "is-unpaid" },
  { label: "Draft", value: 360, tone: "is-draft" },
  { label: "Overdue", value: 280, tone: "is-overdue" }
];

const billingAxisLabels = [400, 300, 200, 100, 0];

function toneByLabel(label) {
  const key = (label || "").toLowerCase();
  if (key === "paid") return "is-paid";
  if (key === "unpaid") return "is-unpaid";
  if (key === "draft") return "is-draft";
  if (key === "overdue") return "is-overdue";
  return "is-paid";
}

export function BillingOverview({ series = [] }) {
  const shouldReduceMotion = useReducedMotion();
  const cardVariants = createCardVariants(shouldReduceMotion);
  const itemVariants = createItemVariants(shouldReduceMotion, "y", 10);
  const hoverLift = createHoverLift(shouldReduceMotion);
  const billingBars = series.length
    ? series.map((item) => ({ label: item.label, value: Number(item.value || 0), tone: toneByLabel(item.label) }))
    : fallbackBillingBars;

  return (
    <motion.section
      className="dashboard-card dashboard-card--billing"
      aria-labelledby="billing-overview-title"
      variants={cardVariants}
      whileHover={hoverLift}
    >
      <div className="dashboard-card__header">
        <h2 id="billing-overview-title">Billing Overview</h2>
      </div>

      <div className="billing-card__body">
        <div className="billing-chart">
          <div className="billing-chart__axis">
            {billingAxisLabels.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>

          <div className="billing-chart__plot">
            <div className="billing-chart__grid">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>

            <div className="billing-chart__bars">
              {billingBars.map((bar, index) => (
                <motion.div key={bar.label} className="billing-bar" variants={itemVariants}>
                  <motion.span
                    className={`billing-bar__fill ${bar.tone}`}
                    initial={shouldReduceMotion ? false : { height: 0 }}
                    animate={{ height: `${(bar.value / 400) * 100}%` }}
                    transition={{ duration: 0.6, delay: shouldReduceMotion ? 0 : 0.08 * index, ease: "easeOut" }}
                  />
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        <div className="billing-summary">
          {billingBars.map((bar) => (
            <motion.article key={bar.label} className="billing-summary__card" variants={itemVariants}>
              <p>
                <span className={`billing-summary__dot ${bar.tone}`} />
                {bar.label}:
              </p>
              <strong>{bar.value}</strong>
            </motion.article>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
