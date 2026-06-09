import Link from "next/link";

export default function Page() {
  return (
    <section className="dashboard-page-stack">
      <div className="dashboard-page-heading">
        <h1>Billing</h1>
        <p className="invoice-page-intro">Use the billing hub to move between invoices and time capture.</p>
      </div>

      <div className="invoice-summary-grid">
        <article className="dashboard-card invoice-summary-card invoice-summary-card--link">
          <span>Invoices</span>
          <strong>Open invoice list, create new invoices, and export PDFs.</strong>
          <Link href="/dashboard/invoices">Go to Invoices</Link>
        </article>
        <article className="dashboard-card invoice-summary-card invoice-summary-card--link">
          <span>Time Entries</span>
          <strong>Review billable work and generate case-based invoice line items.</strong>
          <Link href="/dashboard/time-entries">Go to Time Entries</Link>
        </article>
      </div>
    </section>
  );
}
