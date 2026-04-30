function AvatarStack({ values }) {
  return (
    <div className="avatar-stack">
      {values.map((value) => (
        <span className={`avatar${value.startsWith("+") ? " avatar-more" : ""}`} key={value}>
          {value}
        </span>
      ))}
    </div>
  );
}

function ProgressBar({ value }) {
  return (
    <div className="progress-wrap">
      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${value}%` }} />
      </div>
      <span>{value}%</span>
    </div>
  );
}

export function DataTable({ columns, rows }) {
  return (
    <div className="table-shell">
      <div className="table-toolbar">
        <input className="table-search" type="search" placeholder="Search Project" aria-label="Search Project" />
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.project}-${row.leader}`}>
                <td>
                  <label className="checkbox-cell">
                    <input type="checkbox" aria-label={`Select ${row.project}`} />
                  </label>
                </td>
                <td>
                  <div className="project-cell">
                    <span className="project-badge">{row.project.slice(0, 2).toUpperCase()}</span>
                    <div>
                      <strong>{row.project}</strong>
                      <small>{row.date}</small>
                    </div>
                  </div>
                </td>
                <td>{row.leader}</td>
                <td>
                  <AvatarStack values={row.team} />
                </td>
                <td>
                  <ProgressBar value={row.progress} />
                </td>
                <td>
                  <button className="table-action" type="button">
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
