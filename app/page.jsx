"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ActiveFilesTable } from "../components/dashboard/ActiveFilesTable";
import { BillingOverview } from "../components/dashboard/BillingOverview";
import { CalendarOverview } from "../components/dashboard/CalendarOverview";
import { FinancialOverview } from "../components/dashboard/FinancialOverview";
import { FirmSnapshot } from "../components/dashboard/FirmSnapshot";
import { TodaysOverview } from "../components/dashboard/TodaysOverview";
import { Navbar } from "../components/layout/Navbar";
import { Sidebar } from "../components/layout/Sidebar";
import { createItemVariants, createRowVariants } from "../components/motion";

export default function HomePage() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const shouldReduceMotion = useReducedMotion();
  const rowVariants = createRowVariants(shouldReduceMotion, 0.04);
  const headingVariants = createItemVariants(shouldReduceMotion, "y", 14);

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
          <motion.div
            className="dashboard-page-heading"
            initial="hidden"
            animate="show"
            variants={headingVariants}
          >
            <h1>Dashboard</h1>
          </motion.div>

          <motion.div
            className="dashboard-row-grid"
            initial="hidden"
            animate="show"
            variants={rowVariants}
          >
            <TodaysOverview />
            <FirmSnapshot />
          </motion.div>

          <motion.div
            className="dashboard-row-grid dashboard-row-grid--secondary"
            initial="hidden"
            animate="show"
            variants={rowVariants}
          >
            <CalendarOverview />
            <FinancialOverview />
          </motion.div>

          <motion.div
            className="dashboard-row-grid dashboard-row-grid--tertiary"
            initial="hidden"
            animate="show"
            variants={rowVariants}
          >
            <ActiveFilesTable />
            <BillingOverview />
          </motion.div>
        </section>
      </main>
    </div>
  );
}
