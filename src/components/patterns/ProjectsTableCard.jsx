import { Card } from "../ui/Card";
import { DataTable } from "../ui/DataTable";

const columns = [
  { key: "select", label: "" },
  { key: "project", label: "Project" },
  { key: "leader", label: "Leader" },
  { key: "team", label: "Team" },
  { key: "progress", label: "Progress" },
  { key: "action", label: "Action" }
];

export function ProjectsTableCard({ rows }) {
  return (
    <Card title="Project List" className="table-card">
      <DataTable columns={columns} rows={rows} />
    </Card>
  );
}
