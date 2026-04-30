const statItems = [
  { label: "Due Today", value: 12 },
  { label: "Overdue", value: 4 },
  { label: "Messages", value: 9 }
];

const timelineRows = [
  { label: "JMMB Bank - 103XXX", priority: "High", tone: "is-high" },
  { label: "JMMB Bank - 103XXX", priority: "Low", tone: "is-low" },
  { label: "JMMB Bank - 103XXX", priority: "Normal", tone: "is-normal" }
];

export function TodaysOverview() {
  return (
    <section className="dashboard-card dashboard-card--overview" aria-labelledby="todays-overview-title">
      <div className="dashboard-card__header">
        <h2 id="todays-overview-title">Today&apos;s Overview</h2>
      </div>

      <div className="overview-stats">
        {statItems.map((item) => (
          <article key={item.label} className="overview-stat">
            <p>{item.label}:</p>
            <strong>{item.value}</strong>
          </article>
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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {timelineRows.map((row, index) => (
                <tr key={`${row.priority}-${index}`}>
                  <td>{row.label}</td>
                  <td>
                    <span className={`priority-badge ${row.tone}`}>{row.priority}</span>
                  </td>
                  <td>
                    <button type="button" className="overview-table__action" aria-label={`More actions for ${row.label}`}>
                      <span />
                      <span />
                      <span />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
