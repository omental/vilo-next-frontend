"use client";

import { motion, useReducedMotion } from "framer-motion";
import { createCardVariants, createHoverLift, createItemVariants } from "../motion";

const dayLabels = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

const calendarDates = [
  { value: 28, muted: true },
  { value: 1 },
  { value: 2, active: true },
  { value: 3 },
  { value: 4 },
  { value: 5 },
  { value: 6 },
  { value: 7 },
  { value: 8 },
  { value: 9 },
  { value: 10 },
  { value: 11 },
  { value: 12 },
  { value: 13 },
  { value: 14 },
  { value: 15 },
  { value: 16 },
  { value: 17 },
  { value: 18 },
  { value: 19 },
  { value: 20 },
  { value: 21 },
  { value: 22 },
  { value: 23 },
  { value: 24 },
  { value: 25 },
  { value: 26 },
  { value: 27 },
  { value: 28 },
  { value: 29 },
  { value: 30 },
  { value: 31 },
  { value: 1, muted: true },
  { value: 2, muted: true },
  { value: 3, muted: true }
];

const fallbackEventItems = [
  { color: "is-purple" },
  { color: "is-green" },
  { color: "is-red" },
  { color: "is-orange" },
  { color: "is-purple" },
  { color: "is-gray" }
];

function colorByType(type) {
  if (type === "court") return "is-purple";
  if (type === "meeting") return "is-green";
  if (type === "deadline") return "is-red";
  if (type === "hearing") return "is-orange";
  return "is-gray";
}

export function CalendarOverview({ events = [] }) {
  const shouldReduceMotion = useReducedMotion();
  const cardVariants = createCardVariants(shouldReduceMotion);
  const eventVariants = createItemVariants(shouldReduceMotion, "x", 16);
  const hoverLift = createHoverLift(shouldReduceMotion);
  const eventItems = events.length
    ? events.slice(0, 6).map((item) => ({
        color: colorByType(item.type),
        title: item.title,
        time: item.time,
      }))
    : fallbackEventItems.map((item) => ({ ...item, title: "Miller hearing (Court room)", time: "12:00 PM" }));

  return (
    <motion.section
      className="dashboard-card dashboard-card--calendar"
      aria-labelledby="calendar-overview-title"
      variants={cardVariants}
      whileHover={hoverLift}
    >
      <div className="dashboard-card__header">
        <h2 id="calendar-overview-title">Today&apos;s Overview</h2>
      </div>

      <div className="calendar-overview">
        <div className="calendar-panel">
          <div className="calendar-panel__days">
            {dayLabels.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>

          <div className="calendar-panel__grid">
            {calendarDates.map((date, index) => (
              <div key={`${date.value}-${index}`} className="calendar-panel__cell">
                <span
                  className={[
                    "calendar-panel__date",
                    date.muted ? "is-muted" : "",
                    date.active ? "is-active" : ""
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {date.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="calendar-events">
          {eventItems.map((item, index) => (
            <motion.article
              key={`${item.color}-${index}`}
              className={`calendar-event ${item.color}`}
              variants={eventVariants}
              initial={shouldReduceMotion ? false : "hidden"}
              animate="show"
              transition={{ delay: shouldReduceMotion ? 0 : 0.08 * index }}
            >
              <p>{item.title}</p>
              <span>{item.time}</span>
            </motion.article>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
