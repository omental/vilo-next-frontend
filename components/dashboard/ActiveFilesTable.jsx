const fileRows = [
  {
    fileId: "F-101",
    client: "Apex Group",
    matter: "Corporate Merger",
    lead: "Sarah J.",
    status: "Active",
    due: "Oct 30"
  },
  {
    fileId: "F-102",
    client: "Rahman Holdings",
    matter: "Land Dispute",
    lead: "David K.",
    status: "Active",
    due: "Nov 04"
  },
  {
    fileId: "F-103",
    client: "Blue Ocean Ltd",
    matter: "Contract Review",
    lead: "Maria A.",
    status: "Active",
    due: "Nov 12"
  },
  {
    fileId: "F-104",
    client: "Northline Corp",
    matter: "Employment Matter",
    lead: "Sarah J.",
    status: "Active",
    due: "Nov 20"
  }
];

const tableColumns = ["File ID", "Client", "Matter", "Lead", "Status", "Due"];

export function ActiveFilesTable() {
  return (
    <section className="dashboard-card dashboard-card--files" aria-labelledby="active-files-title">
      <div className="dashboard-card__header">
        <h2 id="active-files-title">Active Files</h2>
      </div>

      <div className="files-table-wrap">
        <table className="files-table">
          <thead>
            <tr>
              {tableColumns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fileRows.map((row) => (
              <tr key={row.fileId}>
                <td>{row.fileId}</td>
                <td>{row.client}</td>
                <td>{row.matter}</td>
                <td>{row.lead}</td>
                <td>
                  <span className="files-status-badge">{row.status}</span>
                </td>
                <td>{row.due}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="files-table__footer">
          <p>Showing 1 to 4 of 4 file records</p>

          <div className="files-pagination" aria-label="Pagination">
            <button type="button" className="files-pagination__button is-arrow" aria-label="Previous page">
              <ChevronLeftIcon />
            </button>
            <button type="button" className="files-pagination__button is-active" aria-current="page">
              1
            </button>
            <button type="button" className="files-pagination__button is-text">Next</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function ChevronLeftIcon() {
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
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}
