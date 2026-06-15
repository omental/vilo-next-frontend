"use client";

import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../../../lib/api";

const accForm = { name: "", bank_name: "", account_number_last4: "", status: "active" };
const txnForm = { trust_account_id: "", client_id: "", case_id: "", amount: "", description: "", transaction_date: "" };
const applyForm = { trust_account_id: "", client_id: "", case_id: "", invoice_id: "", amount: "", description: "" };
const DATE_RANGE_OPTIONS = ["All Dates", "This Month", "Last Month", "This Year"];
const SORT_OPTIONS = ["Client", "Matter", "Balance", "Last Transaction Date"];
const PER_PAGE_OPTIONS = [10, 25, 50];

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function getTodayString() {
  return new Date().toISOString().slice(0, 10);
}

function buildTxnPayload(form) {
  return {
    ...form,
    trust_account_id: Number(form.trust_account_id),
    client_id: Number(form.client_id),
    case_id: form.case_id ? Number(form.case_id) : null,
    amount: Number(form.amount),
  };
}

function buildApplyPayload(form) {
  return {
    ...form,
    trust_account_id: Number(form.trust_account_id),
    client_id: Number(form.client_id),
    case_id: form.case_id ? Number(form.case_id) : null,
    invoice_id: Number(form.invoice_id),
    amount: Number(form.amount),
  };
}

function getSafeErrorMessage(err, fallback) {
  const message = err?.message || "";
  const allowList = [
    "Unauthorized",
    "Insufficient trust balance",
    "Trust account not found",
    "Request failed",
  ];

  return allowList.includes(message) ? message : fallback;
}

function matchesDateRange(dateValue, range) {
  if (!dateValue || range === "All Dates") return true;

  const now = new Date();
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const currentYearStart = new Date(now.getFullYear(), 0, 1);
  const rowDate = new Date(dateValue);

  if (Number.isNaN(rowDate.getTime())) return range === "All Dates";
  if (range === "This Month") return rowDate >= currentMonthStart && rowDate < nextMonthStart;
  if (range === "Last Month") return rowDate >= lastMonthStart && rowDate < currentMonthStart;
  if (range === "This Year") return rowDate >= currentYearStart && rowDate < nextMonthStart;
  return true;
}

function isCurrentMonth(dateValue) {
  if (!dateValue) return false;
  const date = new Date(dateValue);
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
}

function payoutAmount(txn) {
  const amount = Number(txn.amount || 0);
  if (["refund", "disbursement", "applied_to_invoice"].includes(txn.transaction_type)) return Math.abs(amount);
  if (txn.transaction_type === "adjustment" && amount < 0) return Math.abs(amount);
  return 0;
}

function depositAmount(txn) {
  const amount = Number(txn.amount || 0);
  if (txn.transaction_type === "deposit") return Math.abs(amount);
  if (txn.transaction_type === "adjustment" && amount > 0) return amount;
  return 0;
}

function findLedgerTransactions(txns, ledger) {
  return txns
    .filter((txn) => Number(txn.trust_account_id) === Number(ledger.trust_account_id)
      && Number(txn.client_id) === Number(ledger.client_id)
      && Number(txn.case_id || 0) === Number(ledger.case_id || 0))
    .sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime());
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="5" cy="12" r="1.8" fill="currentColor" />
      <circle cx="12" cy="12" r="1.8" fill="currentColor" />
      <circle cx="19" cy="12" r="1.8" fill="currentColor" />
    </svg>
  );
}

function ArrowLeftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 18l-6-6 6-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function MoneyIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="6" width="16" height="12" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 12h6M12 9v6" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8.25" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8.8 12.1l2.25 2.3 4.2-4.8" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function Modal({ title, copy, onClose, children }) {
  return (
    <div className="vilo-modal-overlay" onClick={onClose}>
      <div className="vilo-modal trust-modal" onClick={(event) => event.stopPropagation()}>
        <div className="vilo-modal__header">
          <div>
            <h3>{title}</h3>
            {copy ? <p className="trust-modal__copy">{copy}</p> : null}
          </div>
          <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={onClose}>Close</button>
        </div>
        <div className="vilo-modal__body">{children}</div>
      </div>
    </div>
  );
}

export default function TrustPage() {
  const [accounts, setAccounts] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [txns, setTxns] = useState([]);
  const [clients, setClients] = useState([]);
  const [cases, setCases] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [modal, setModal] = useState("");
  const [activeLedger, setActiveLedger] = useState(null);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [dateRange, setDateRange] = useState("All Dates");
  const [sortBy, setSortBy] = useState("Client");
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);
  const [aForm, setAForm] = useState(accForm);
  const [dForm, setDForm] = useState(txnForm);
  const [rForm, setRForm] = useState(txnForm);
  const [xForm, setXForm] = useState(txnForm);
  const [apForm, setApForm] = useState(applyForm);

  async function load() {
    setLoading(true);
    setError("");

    try {
      const [a, l, t, c, cs, i, s] = await Promise.all([
        apiRequest("/api/v1/trust/accounts"),
        apiRequest("/api/v1/trust/ledgers"),
        apiRequest("/api/v1/trust/transactions"),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/cases").catch(() => []),
        apiRequest("/api/v1/invoices").catch(() => []),
        apiRequest("/api/v1/trust/reconciliation-summary").catch(() => null),
      ]);
      setAccounts(a || []);
      setLedgers(l || []);
      setTxns(t || []);
      setClients(c || []);
      setCases(cs || []);
      setInvoices(i || []);
      setSummary(s);
    } catch {
      setError("Unable to load trust accounting data right now. Please retry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!menuOpenId) return undefined;

    function closeMenu() {
      setMenuOpenId(null);
    }

    window.addEventListener("click", closeMenu);
    return () => window.removeEventListener("click", closeMenu);
  }, [menuOpenId]);

  const accountsById = useMemo(
    () => Object.fromEntries(accounts.map((row) => [Number(row.id), row])),
    [accounts],
  );

  const clientsById = useMemo(
    () => Object.fromEntries(clients.map((row) => [Number(row.id), row])),
    [clients],
  );

  const casesById = useMemo(
    () => Object.fromEntries(cases.map((row) => [Number(row.id), row])),
    [cases],
  );

  const invoicesById = useMemo(
    () => Object.fromEntries(invoices.map((row) => [Number(row.id), row])),
    [invoices],
  );

  const statTotals = useMemo(() => {
    return txns.reduce((acc, txn) => {
      if (!isCurrentMonth(txn.transaction_date)) return acc;
      acc.deposits += depositAmount(txn);
      acc.payouts += payoutAmount(txn);
      return acc;
    }, { deposits: 0, payouts: 0 });
  }, [txns]);

  const ledgerRows = useMemo(() => {
    return ledgers.map((ledger) => {
      const client = clientsById[Number(ledger.client_id)];
      const matter = ledger.case_id ? casesById[Number(ledger.case_id)] : null;
      const account = accountsById[Number(ledger.trust_account_id)];
      const transactions = findLedgerTransactions(txns, ledger);
      const lastTransaction = transactions[0] || null;

      return {
        ...ledger,
        clientName: client?.name || `Client #${ledger.client_id}`,
        matterName: matter?.title || "No matter linked",
        trustAccountLabel: account?.bank_name || account?.name || `Trust #${ledger.trust_account_id}`,
        trustAccountName: account?.name || `Trust #${ledger.trust_account_id}`,
        lastTransactionDate: lastTransaction?.transaction_date || null,
        transactions,
      };
    });
  }, [accountsById, casesById, clientsById, ledgers, txns]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    const nextRows = ledgerRows.filter((row) => {
      const haystack = [
        row.clientName,
        row.matterName,
        row.trustAccountLabel,
        row.trustAccountName,
      ].join(" ").toLowerCase();
      return (!query || haystack.includes(query)) && matchesDateRange(row.lastTransactionDate, dateRange);
    });

    nextRows.sort((left, right) => {
      if (sortBy === "Balance") return Number(right.current_balance || 0) - Number(left.current_balance || 0);
      if (sortBy === "Matter") return left.matterName.localeCompare(right.matterName);
      if (sortBy === "Last Transaction Date") {
        return new Date(right.lastTransactionDate || 0).getTime() - new Date(left.lastTransactionDate || 0).getTime();
      }
      return left.clientName.localeCompare(right.clientName);
    });

    return nextRows;
  }, [dateRange, ledgerRows, search, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / perPage));
  const currentPage = Math.min(page, totalPages);
  const paginatedRows = filteredRows.slice((currentPage - 1) * perPage, currentPage * perPage);

  useEffect(() => {
    setPage(1);
  }, [search, dateRange, sortBy, perPage]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  function closeModal() {
    setModal("");
    setActiveLedger(null);
    setFormError("");
  }

  function openCreateAccount() {
    setAForm(accForm);
    setFormError("");
    setModal("account");
  }

  function openDeposit(ledger = null) {
    setActiveLedger(ledger);
    setDForm({
      ...txnForm,
      trust_account_id: ledger ? String(ledger.trust_account_id) : "",
      client_id: ledger ? String(ledger.client_id) : "",
      case_id: ledger?.case_id ? String(ledger.case_id) : "",
      transaction_date: getTodayString(),
    });
    setFormError("");
    setModal("deposit");
  }

  function openWithdrawal(ledger = null) {
    setActiveLedger(ledger);
    setXForm({
      ...txnForm,
      trust_account_id: ledger ? String(ledger.trust_account_id) : "",
      client_id: ledger ? String(ledger.client_id) : "",
      case_id: ledger?.case_id ? String(ledger.case_id) : "",
      transaction_date: getTodayString(),
    });
    setFormError("");
    setModal("withdrawal");
  }

  function openRefund(ledger) {
    setActiveLedger(ledger);
    setRForm({
      ...txnForm,
      trust_account_id: String(ledger.trust_account_id),
      client_id: String(ledger.client_id),
      case_id: ledger.case_id ? String(ledger.case_id) : "",
      transaction_date: getTodayString(),
    });
    setFormError("");
    setModal("refund");
  }

  function openApplyToInvoice(ledger) {
    setActiveLedger(ledger);
    setApForm({
      ...applyForm,
      trust_account_id: String(ledger.trust_account_id),
      client_id: String(ledger.client_id),
      case_id: ledger.case_id ? String(ledger.case_id) : "",
    });
    setFormError("");
    setModal("apply");
  }

  function openTransactions(ledger) {
    setActiveLedger(ledger);
    setFormError("");
    setModal("transactions");
  }

  async function createAccount(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");

    try {
      await apiRequest("/api/v1/trust/accounts", { method: "POST", body: JSON.stringify(aForm) });
      setAForm(accForm);
      closeModal();
      await load();
    } catch (err) {
      setFormError(getSafeErrorMessage(err, "Unable to create the trust account right now."));
    } finally {
      setSaving(false);
    }
  }

  async function submitTransaction(path, form, reset, successModalClose = true) {
    setSaving(true);
    setFormError("");

    try {
      await apiRequest(path, { method: "POST", body: JSON.stringify(buildTxnPayload(form)) });
      reset(txnForm);
      if (successModalClose) closeModal();
      await load();
    } catch (err) {
      setFormError(getSafeErrorMessage(err, "Unable to save the trust transaction right now."));
    } finally {
      setSaving(false);
    }
  }

  async function submitApplyToInvoice(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");

    try {
      await apiRequest("/api/v1/trust/apply-to-invoice", {
        method: "POST",
        body: JSON.stringify(buildApplyPayload(apForm)),
      });
      setApForm(applyForm);
      closeModal();
      await load();
    } catch (err) {
      setFormError(getSafeErrorMessage(err, "Unable to apply trust funds to the invoice right now."));
    } finally {
      setSaving(false);
    }
  }

  const activeLedgerTransactions = activeLedger ? findLedgerTransactions(txns, activeLedger) : [];
  const filteredInvoices = activeLedger
    ? invoices.filter((invoice) => Number(invoice.client_id) === Number(activeLedger.client_id))
    : invoices;

  return (
    <section className="dashboard-page-stack trust-page">
      <div className="trust-page__top">
        <div className="dashboard-page-heading">
          <h1>Trust Accounting</h1>
          <p className="trust-page__intro">Monitor client trust balances, review matter activity, and record movements without changing the underlying ledger workflow.</p>
        </div>
        <div className="trust-page__actions">
          <button type="button" className="vilo-btn vilo-btn--secondary" onClick={openCreateAccount}>New Trust Account</button>
          <button type="button" className="vilo-btn trust-page__withdraw-button" onClick={() => openWithdrawal()}>
            + Record Withdrawal
          </button>
        </div>
      </div>

      {error ? (
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">{error}</p>
          <button type="button" className="vilo-btn vilo-btn--secondary trust-page__retry" onClick={load}>Retry</button>
        </div>
      ) : null}

      <div className="trust-summary-grid">
        <article className="dashboard-card trust-stat-card">
          <div>
            <p>Trust Deposits This Month</p>
            <strong>{formatMoney(statTotals.deposits)}</strong>
          </div>
          <span className="trust-stat-card__icon trust-stat-card__icon--violet" aria-hidden="true">
            <MoneyIcon />
          </span>
        </article>
        <article className="dashboard-card trust-stat-card">
          <div>
            <p>Trust Payouts This Month</p>
            <strong>{formatMoney(statTotals.payouts)}</strong>
          </div>
          <span className="trust-stat-card__icon trust-stat-card__icon--mint" aria-hidden="true">
            <CheckIcon />
          </span>
        </article>
      </div>

      {summary ? (
        <div className="trust-summary-strip">
          <span>Total Trust Balance {formatMoney(summary.total_trust_account_balance)}</span>
          <span>Client Ledgers {formatMoney(summary.total_client_ledger_balances)}</span>
          <span>Matter Balances {formatMoney(summary.total_matter_case_balances)}</span>
          <span className={summary.matches ? "is-good" : "is-warning"}>{summary.matches ? "Reconciliation matched" : "Reconciliation needs review"}</span>
        </div>
      ) : null}

      <article className="dashboard-card vilo-table-card trust-shell-card">
        <div className="trust-toolbar">
          <div className="trust-search-group">
            <label className="trust-search-input">
              <SearchIcon />
              <input
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    setSearch(searchDraft);
                  }
                }}
                placeholder="Search client, matter, or account"
                type="search"
              />
            </label>
            <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => setSearch(searchDraft)}>Search</button>
          </div>

          <div className="trust-filter-group">
            <label className="trust-filter-field">
              <span>Date Range:</span>
              <select value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
                {DATE_RANGE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="trust-filter-field">
              <span>Sort By:</span>
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                {SORT_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="trust-filter-field">
              <span>Per Page:</span>
              <select value={perPage} onChange={(event) => setPerPage(Number(event.target.value))}>
                {PER_PAGE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
          </div>
        </div>

        <div className="dashboard-card__header trust-table-header">
          <h2>Current Client Trust Balances</h2>
          <button type="button" className="trust-shell-card__deposit" onClick={() => openDeposit()}>Record Deposit</button>
        </div>

        {loading ? (
          <div className="vilo-state-block trust-state-block">
            <p className="vilo-state vilo-state--loading">Loading trust balances...</p>
          </div>
        ) : null}

        {!loading && !filteredRows.length ? (
          <div className="vilo-state-block trust-state-block">
            <p className="vilo-state">No trust balances are available for the current filters.</p>
          </div>
        ) : null}

        {!loading && !!filteredRows.length ? (
          <>
            <div className={`vilo-table-wrap case-table-wrap trust-table-wrap${menuOpenId ? " case-table-wrap--menu-visible" : ""}`}>
              <table className="team-table trust-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Matter</th>
                    <th>In Trust</th>
                    <th>Trust Account</th>
                    <th>Last Transaction Date</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <div className="trust-table__primary">
                          <strong>{row.clientName}</strong>
                        </div>
                      </td>
                      <td>{row.matterName}</td>
                      <td>{formatMoney(row.current_balance)}</td>
                      <td>
                        <div className="trust-table__primary">
                          <strong>{row.trustAccountLabel}</strong>
                          <span>{row.trustAccountName}</span>
                        </div>
                      </td>
                      <td>{formatDate(row.lastTransactionDate)}</td>
                      <td>
                        <div className="vilo-table-actions trust-row-actions">
                          <button
                            type="button"
                            className="vilo-btn vilo-btn--ghost vilo-btn--xs trust-row-actions__trigger"
                            aria-expanded={menuOpenId === row.id}
                            onClick={(event) => {
                              event.stopPropagation();
                              setMenuOpenId((current) => (current === row.id ? null : row.id));
                            }}
                          >
                            <DotsIcon />
                          </button>
                          {menuOpenId === row.id ? (
                            <div className="case-actions-menu trust-actions-menu" onClick={(event) => event.stopPropagation()}>
                              <button type="button" onClick={() => { setMenuOpenId(null); openTransactions(row); }}>View transactions</button>
                              <button type="button" onClick={() => { setMenuOpenId(null); openDeposit(row); }}>Record deposit</button>
                              <button type="button" onClick={() => { setMenuOpenId(null); openWithdrawal(row); }}>Record withdrawal</button>
                              <button type="button" onClick={() => { setMenuOpenId(null); openRefund(row); }}>Record refund</button>
                              <button type="button" onClick={() => { setMenuOpenId(null); openApplyToInvoice(row); }}>Apply to invoice</button>
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="trust-table-footer">
              <p>Showing {(currentPage - 1) * perPage + 1} to {Math.min(currentPage * perPage, filteredRows.length)} of {filteredRows.length} trust balances</p>
              <div className="time-entries-pagination">
                <button type="button" className="time-entries-pagination__nav" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} aria-label="Previous page">
                  <ArrowLeftIcon />
                </button>
                <button type="button" className="time-entries-pagination__page is-active">{currentPage}</button>
                <button type="button" className="time-entries-pagination__next" disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>Next</button>
              </div>
            </div>
          </>
        ) : null}
      </article>

      {modal === "account" ? (
        <Modal title="Create Trust Account" copy="Creates a tenant-scoped trust account using the existing trust account API." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={createAccount}>
            <input placeholder="Account name" value={aForm.name} onChange={(event) => setAForm({ ...aForm, name: event.target.value })} required />
            <input placeholder="Bank name" value={aForm.bank_name} onChange={(event) => setAForm({ ...aForm, bank_name: event.target.value })} />
            <input placeholder="Last 4 digits" maxLength={4} value={aForm.account_number_last4} onChange={(event) => setAForm({ ...aForm, account_number_last4: event.target.value })} />
            <div className="vilo-table-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Create Account"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "deposit" ? (
        <Modal title="Record Deposit" copy="Posts a deposit to the existing trust deposit endpoint." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={(event) => { event.preventDefault(); submitTransaction("/api/v1/trust/deposit", dForm, setDForm); }}>
            <div className="vilo-form-row-two">
              <select value={dForm.trust_account_id} onChange={(event) => setDForm({ ...dForm, trust_account_id: event.target.value })} required>
                <option value="">Trust account</option>
                {accounts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <select value={dForm.client_id} onChange={(event) => setDForm({ ...dForm, client_id: event.target.value, case_id: "" })} required>
                <option value="">Client</option>
                {clients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <select value={dForm.case_id} onChange={(event) => setDForm({ ...dForm, case_id: event.target.value })}>
                <option value="">Matter (optional)</option>
                {cases.filter((row) => !dForm.client_id || Number(row.client_id) === Number(dForm.client_id)).map((row) => (
                  <option key={row.id} value={row.id}>{row.title}</option>
                ))}
              </select>
              <input type="number" step="0.01" placeholder="Amount" value={dForm.amount} onChange={(event) => setDForm({ ...dForm, amount: event.target.value })} required />
            </div>
            <input type="date" value={dForm.transaction_date} onChange={(event) => setDForm({ ...dForm, transaction_date: event.target.value })} required />
            <textarea placeholder="Description" value={dForm.description} onChange={(event) => setDForm({ ...dForm, description: event.target.value })} />
            <div className="vilo-table-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Record Deposit"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "withdrawal" ? (
        <Modal title="Record Withdrawal" copy="This uses the existing trust disbursement flow and keeps current validation intact." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={(event) => { event.preventDefault(); submitTransaction("/api/v1/trust/disbursement", xForm, setXForm); }}>
            <div className="vilo-form-row-two">
              <select value={xForm.trust_account_id} onChange={(event) => setXForm({ ...xForm, trust_account_id: event.target.value })} required>
                <option value="">Trust account</option>
                {accounts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <select value={xForm.client_id} onChange={(event) => setXForm({ ...xForm, client_id: event.target.value, case_id: "" })} required>
                <option value="">Client</option>
                {clients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <select value={xForm.case_id} onChange={(event) => setXForm({ ...xForm, case_id: event.target.value })}>
                <option value="">Matter (optional)</option>
                {cases.filter((row) => !xForm.client_id || Number(row.client_id) === Number(xForm.client_id)).map((row) => (
                  <option key={row.id} value={row.id}>{row.title}</option>
                ))}
              </select>
              <input type="number" step="0.01" placeholder="Amount" value={xForm.amount} onChange={(event) => setXForm({ ...xForm, amount: event.target.value })} required />
            </div>
            <input type="date" value={xForm.transaction_date} onChange={(event) => setXForm({ ...xForm, transaction_date: event.target.value })} required />
            <textarea placeholder="Description" value={xForm.description} onChange={(event) => setXForm({ ...xForm, description: event.target.value })} />
            <div className="vilo-table-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Record Withdrawal"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "refund" ? (
        <Modal title="Record Refund" copy="Refunds remain available through the original trust refund endpoint." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={(event) => { event.preventDefault(); submitTransaction("/api/v1/trust/refund", rForm, setRForm); }}>
            <div className="vilo-form-row-two">
              <select value={rForm.trust_account_id} onChange={(event) => setRForm({ ...rForm, trust_account_id: event.target.value })} required>
                <option value="">Trust account</option>
                {accounts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <select value={rForm.client_id} onChange={(event) => setRForm({ ...rForm, client_id: event.target.value, case_id: "" })} required>
                <option value="">Client</option>
                {clients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <select value={rForm.case_id} onChange={(event) => setRForm({ ...rForm, case_id: event.target.value })}>
                <option value="">Matter (optional)</option>
                {cases.filter((row) => !rForm.client_id || Number(row.client_id) === Number(rForm.client_id)).map((row) => (
                  <option key={row.id} value={row.id}>{row.title}</option>
                ))}
              </select>
              <input type="number" step="0.01" placeholder="Amount" value={rForm.amount} onChange={(event) => setRForm({ ...rForm, amount: event.target.value })} required />
            </div>
            <input type="date" value={rForm.transaction_date} onChange={(event) => setRForm({ ...rForm, transaction_date: event.target.value })} required />
            <textarea placeholder="Description" value={rForm.description} onChange={(event) => setRForm({ ...rForm, description: event.target.value })} />
            <div className="vilo-table-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Record Refund"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "apply" ? (
        <Modal title="Apply Trust To Invoice" copy="Applies trust funds using the existing invoice allocation flow." onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitApplyToInvoice}>
            <div className="vilo-form-row-two">
              <select value={apForm.trust_account_id} onChange={(event) => setApForm({ ...apForm, trust_account_id: event.target.value })} required>
                <option value="">Trust account</option>
                {accounts.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
              <select value={apForm.client_id} onChange={(event) => setApForm({ ...apForm, client_id: event.target.value, case_id: "", invoice_id: "" })} required>
                <option value="">Client</option>
                {clients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <select value={apForm.case_id} onChange={(event) => setApForm({ ...apForm, case_id: event.target.value })}>
                <option value="">Matter (optional)</option>
                {cases.filter((row) => !apForm.client_id || Number(row.client_id) === Number(apForm.client_id)).map((row) => (
                  <option key={row.id} value={row.id}>{row.title}</option>
                ))}
              </select>
              <select value={apForm.invoice_id} onChange={(event) => setApForm({ ...apForm, invoice_id: event.target.value })} required>
                <option value="">Invoice</option>
                {filteredInvoices.map((row) => (
                  <option key={row.id} value={row.id}>{row.invoice_number || `Invoice #${row.id}`}</option>
                ))}
              </select>
            </div>
            <input type="number" step="0.01" placeholder="Amount" value={apForm.amount} onChange={(event) => setApForm({ ...apForm, amount: event.target.value })} required />
            <textarea placeholder="Description" value={apForm.description} onChange={(event) => setApForm({ ...apForm, description: event.target.value })} />
            <div className="vilo-table-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Apply Funds"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "transactions" ? (
        <Modal
          title={activeLedger ? `${activeLedger.clientName} Trust Activity` : "Trust Activity"}
          copy="This is a filtered view of the transactions already loaded for the selected ledger."
          onClose={closeModal}
        >
          {!activeLedgerTransactions.length ? (
            <div className="vilo-state-block trust-state-block trust-state-block--modal">
              <p className="vilo-state">No transactions were found for this client trust balance.</p>
            </div>
          ) : (
            <div className="vilo-table-wrap trust-modal__table-wrap">
              <table className="team-table trust-transactions-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Invoice</th>
                  </tr>
                </thead>
                <tbody>
                  {activeLedgerTransactions.map((txn) => (
                    <tr key={txn.id}>
                      <td>{txn.transaction_type.replaceAll("_", " ")}</td>
                      <td>{formatMoney(txn.amount)}</td>
                      <td>{formatDate(txn.transaction_date)}</td>
                      <td>{txn.description || "-"}</td>
                      <td>{txn.invoice_id ? (invoicesById[Number(txn.invoice_id)]?.invoice_number || `Invoice #${txn.invoice_id}`) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Modal>
      ) : null}
    </section>
  );
}
