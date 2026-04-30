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

const eventItems = [
  { color: "is-purple" },
  { color: "is-green" },
  { color: "is-red" },
  { color: "is-orange" },
  { color: "is-purple" },
  { color: "is-gray" }
];

export function CalendarOverview() {
  return (
    <section className="dashboard-card dashboard-card--calendar" aria-labelledby="calendar-overview-title">
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
            <article key={`${item.color}-${index}`} className={`calendar-event ${item.color}`}>
              <p>Miller hearing (Court room)</p>
              <span>12:00 PM</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
