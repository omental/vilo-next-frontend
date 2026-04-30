export function DashboardShell({ sidebar, navbar, children }) {
  return (
    <div className="dashboard-shell">
      {sidebar}
      <div className="dashboard-main">
        {navbar}
        <main className="dashboard-content">{children}</main>
      </div>
    </div>
  );
}
