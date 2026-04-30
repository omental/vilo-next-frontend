"use client";

import { useState } from "react";
import { ActiveFilesTable } from "../components/dashboard/ActiveFilesTable";
import { BillingOverview } from "../components/dashboard/BillingOverview";
import { CalendarOverview } from "../components/dashboard/CalendarOverview";
import { FinancialOverview } from "../components/dashboard/FinancialOverview";
import { FirmSnapshot } from "../components/dashboard/FirmSnapshot";
import { TodaysOverview } from "../components/dashboard/TodaysOverview";
import { Navbar } from "../components/layout/Navbar";
import { Sidebar } from "../components/layout/Sidebar";

export default function HomePage() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  return (
    <div className="dashboard-shell">
      <div
        className={`mobile-sidebar-overlay${isMobileSidebarOpen ? " is-visible" : ""}`}
        onClick={() => setIsMobileSidebarOpen(false)}
        aria-hidden="true"
      />
      <Sidebar isMobileOpen={isMobileSidebarOpen} />
      <main className="dashboard-main">
        <Navbar onMobileMenuClick={() => setIsMobileSidebarOpen(true)} />
        <section className="dashboard-home" aria-label="Dashboard content">
          <div className="dashboard-page-heading">
            <h1>Dashboard</h1>
          </div>

          <div className="dashboard-row-grid">
            <TodaysOverview />
            <FirmSnapshot />
          </div>

          <div className="dashboard-row-grid dashboard-row-grid--secondary">
            <CalendarOverview />
            <FinancialOverview />
          </div>

          <div className="dashboard-row-grid dashboard-row-grid--tertiary">
            <ActiveFilesTable />
            <BillingOverview />
          </div>
        </section>
      </main>
    </div>
  );
}
