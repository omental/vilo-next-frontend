"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getCachedUser, setCachedUser } from "../../../lib/auth";
import { apiRequest } from "../../../lib/api";

const TAB_OPTIONS = ["transactions", "client_ledgers", "matter_ledgers", "receipts", "reconciliation"];
const MODAL_DEFAULTS = {
  deposit: {
    trust_account_id: "",
    client_id: "",
    case_id: "",
    amount: "",
    currency: "USD",
    transaction_date: "",
    payment_method: "",
    reference_number: "",
    description: "",
    payee_name: "",
    payee_type: "",
    adjustment_direction: "increase",
    adjustment_reason: "",
  },
  disbursement: {
    trust_account_id: "",
    client_id: "",
    case_id: "",
    amount: "",
    currency: "USD",
    transaction_date: "",
    payment_method: "",
    reference_number: "",
    description: "",
    payee_name: "",
    payee_type: "",
    adjustment_direction: "increase",
    adjustment_reason: "",
  },
  refund: {
    trust_account_id: "",
    client_id: "",
    case_id: "",
    amount: "",
    currency: "USD",
    transaction_date: "",
    payment_method: "",
    reference_number: "",
    description: "",
    payee_name: "",
    payee_type: "",
    adjustment_direction: "increase",
    adjustment_reason: "",
  },
  adjustment: {
    trust_account_id: "",
    client_id: "",
    case_id: "",
    amount: "",
    currency: "USD",
    transaction_date: "",
    payment_method: "",
    reference_number: "",
    description: "",
    payee_name: "",
    payee_type: "",
    adjustment_direction: "increase",
    adjustment_reason: "",
  },
};

function roleCanManage(role) {
  return role === "partner" || role === "admin";
}

function formatMoney(value, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function buildSearch(path, params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "" || value === false) return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function txStatus(txn) {
  if (txn.voided_at) return "voided";
  if (txn.reversal_of_id) return "reversal";
  return "active";
}

function txDirection(txn) {
  if (txn.transaction_type === "deposit") return "inflow";
  if (txn.transaction_type === "adjustment") return txn.adjustment_direction === "decrease" ? "outflow" : "inflow";
  return "outflow";
}

function txTypeLabel(txn) {
  if (txn.reversal_of_id) return "Reversal adjustment";
  return txn.transaction_type.replaceAll("_", " ");
}

function sectionCopy(modal) {
  if (modal === "deposit") return "Client funds are held in trust and remain separate from firm operating revenue.";
  if (modal === "disbursement") return "Use disbursement only for third-party payouts from trust. Revenue is not created here.";
  if (modal === "refund") return "Refund returns unused client funds from trust. It does not affect invoice revenue or tax.";
  if (modal === "adjustment") return "Adjustment is an audited correction entry. It does not edit prior trust transactions.";
  if (modal === "void") return "Voiding preserves history and creates a reversal. Transactions are not deleted.";
  return "";
}

function EmptyState({ message }) {
  return (
    <div className="vilo-state-block trust-state-block">
      <p className="vilo-state">{message}</p>
    </div>
  );
}

function Modal({ title, copy, onClose, children }) {
  return (
    <div className="vilo-modal-overlay" onClick={onClose}>
      <div className="vilo-modal trust-modal trust-modal--wide" onClick={(event) => event.stopPropagation()}>
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

function TrustPageInner() {
  const searchParams = useSearchParams();
  const [currentUser, setCurrentUser] = useState(getCachedUser());
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [clientLedgers, setClientLedgers] = useState([]);
  const [matterLedgers, setMatterLedgers] = useState([]);
  const [clients, setClients] = useState([]);
  const [cases, setCases] = useState([]);
  const [balances, setBalances] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [activeTab, setActiveTab] = useState("transactions");
  const [currency, setCurrency] = useState("USD");
  const [includeVoided, setIncludeVoided] = useState(true);
  const [modal, setModal] = useState("");
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [voidReason, setVoidReason] = useState("");
  const [forms, setForms] = useState(MODAL_DEFAULTS);

  const queryClientId = searchParams.get("client_id") || "";
  const queryCaseId = searchParams.get("case_id") || "";
  const queryAction = searchParams.get("action") || "";

  useEffect(() => {
    if (currentUser) return;
    let cancelled = false;
    apiRequest("/api/v1/auth/me")
      .then((me) => {
        if (cancelled) return;
        setCurrentUser(me);
        setCachedUser(me);
      })
      .catch(() => {
        if (cancelled) return;
        setCurrentUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  const filteredCases = useMemo(() => {
    if (!queryClientId) return cases;
    return cases.filter((row) => Number(row.client_id) === Number(queryClientId));
  }, [cases, queryClientId]);

  const availableCurrencies = useMemo(() => {
    const next = new Set(["USD"]);
    accounts.forEach((row) => next.add((row.currency || "USD").toUpperCase()));
    clientLedgers.forEach((row) => next.add((row.currency || "USD").toUpperCase()));
    matterLedgers.forEach((row) => next.add((row.currency || "USD").toUpperCase()));
    transactions.forEach((row) => next.add((row.currency || "USD").toUpperCase()));
    return Array.from(next);
  }, [accounts, clientLedgers, matterLedgers, transactions]);

  useEffect(() => {
    if (!availableCurrencies.includes(currency)) {
      setCurrency(availableCurrencies[0] || "USD");
    }
  }, [availableCurrencies, currency]);

  async function loadData(nextCurrency = currency, opts = { initial: false }) {
    if (opts.initial) setLoading(true);
    else setRefreshing(true);
    setError("");
    try {
      const txPath = buildSearch("/api/v1/trust/transactions", {
        currency: nextCurrency,
        client_id: queryClientId || undefined,
        case_id: queryCaseId || undefined,
        include_voided: includeVoided,
      });
      const balancesPath = buildSearch("/api/v1/trust/balances", {
        currency: nextCurrency,
        client_id: queryClientId || undefined,
        case_id: queryCaseId || undefined,
      });
      const [accountRows, txRows, clientRows, matterRows, clientList, caseList, balanceRow] = await Promise.all([
        apiRequest("/api/v1/trust/accounts"),
        apiRequest(txPath),
        apiRequest(buildSearch("/api/v1/trust/client-ledgers", { currency: nextCurrency })),
        apiRequest(buildSearch("/api/v1/trust/matter-ledgers", { currency: nextCurrency })),
        apiRequest("/api/v1/clients"),
        apiRequest("/api/v1/cases").catch(() => []),
        apiRequest(balancesPath).catch(() => null),
      ]);
      setAccounts(accountRows || []);
      setTransactions(txRows || []);
      setClientLedgers(clientRows || []);
      setMatterLedgers(matterRows || []);
      setClients(clientList || []);
      setCases(caseList || []);
      setBalances(balanceRow);
    } catch (err) {
      setError(err.message || "Unable to load trust accounting.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadData(currency, { initial: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) loadData(currency);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currency, includeVoided, queryClientId, queryCaseId]);

  useEffect(() => {
    if (!queryAction) return;
    if (["deposit", "disbursement", "refund", "adjustment"].includes(queryAction)) {
      openTransactionModal(queryAction);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryAction, clients.length, cases.length, accounts.length]);

  const canManage = roleCanManage(currentUser?.role || "");
  const unauthorized = currentUser && !["partner", "admin", "lawyer", "paralegal"].includes(currentUser.role);

  const clientById = useMemo(() => Object.fromEntries(clients.map((row) => [Number(row.id), row])), [clients]);
  const caseById = useMemo(() => Object.fromEntries(cases.map((row) => [Number(row.id), row])), [cases]);
  const accountById = useMemo(() => Object.fromEntries(accounts.map((row) => [Number(row.id), row])), [accounts]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((txn) => {
      if ((txn.currency || "USD").toUpperCase() !== currency) return false;
      if (queryClientId && Number(txn.client_id) !== Number(queryClientId)) return false;
      if (queryCaseId && Number(txn.case_id) !== Number(queryCaseId)) return false;
      return true;
    });
  }, [currency, queryCaseId, queryClientId, transactions]);

  const filteredClientLedgers = useMemo(() => {
    return clientLedgers.filter((row) => (row.currency || "USD").toUpperCase() === currency);
  }, [clientLedgers, currency]);

  const filteredMatterLedgers = useMemo(() => {
    return matterLedgers.filter((row) => {
      if ((row.currency || "USD").toUpperCase() !== currency) return false;
      if (queryClientId && Number(row.client_id) !== Number(queryClientId)) return false;
      if (queryCaseId && Number(row.case_id) !== Number(queryCaseId)) return false;
      return true;
    });
  }, [currency, matterLedgers, queryCaseId, queryClientId]);

  const depositReceipts = useMemo(() => {
    return filteredTransactions.filter((txn) => txn.receipt_id);
  }, [filteredTransactions]);

  const summaryTotals = useMemo(() => {
    const totalTrustBalance = accounts
      .filter((row) => (row.currency || "USD").toUpperCase() === currency)
      .reduce((sum, row) => sum + Number(row.current_balance || 0), 0);
    const clientTotal = filteredClientLedgers.reduce((sum, row) => sum + Number(row.balance || 0), 0);
    const matterTotal = filteredMatterLedgers.reduce((sum, row) => sum + Number(row.balance || 0), 0);
    return { totalTrustBalance, clientTotal, matterTotal };
  }, [accounts, currency, filteredClientLedgers, filteredMatterLedgers]);

  function syncModalForm(type, overrides = {}) {
    const defaultAccount = accounts.find((row) => (row.currency || "USD").toUpperCase() === currency)?.id || "";
    const nextClientId = queryClientId || overrides.client_id || "";
    const nextCaseId = queryCaseId || overrides.case_id || "";
    setForms((current) => ({
      ...current,
      [type]: {
        ...MODAL_DEFAULTS[type],
        trust_account_id: defaultAccount ? String(defaultAccount) : "",
        client_id: nextClientId ? String(nextClientId) : "",
        case_id: nextCaseId ? String(nextCaseId) : "",
        currency,
        transaction_date: today(),
        ...overrides,
      },
    }));
  }

  function openTransactionModal(type, overrides = {}) {
    syncModalForm(type, overrides);
    setSelectedTransaction(null);
    setSelectedReceipt(null);
    setVoidReason("");
    setFormError("");
    setModal(type);
  }

  function closeModal() {
    setModal("");
    setSelectedReceipt(null);
    setSelectedTransaction(null);
    setVoidReason("");
    setFormError("");
  }

  function updateForm(type, field, value) {
    setForms((current) => {
      const next = { ...current[type], [field]: value };
      if (field === "trust_account_id") {
        const account = accountById[Number(value)];
        if (account?.currency) next.currency = account.currency;
      }
      if (field === "client_id") next.case_id = "";
      return { ...current, [type]: next };
    });
  }

  async function submitTransaction(event, type) {
    event.preventDefault();
    const form = forms[type];
    setSaving(true);
    setFormError("");
    try {
      const payload = {
        trust_account_id: Number(form.trust_account_id),
        client_id: Number(form.client_id),
        case_id: Number(form.case_id),
        transaction_type: type,
        amount: Number(form.amount),
        currency: form.currency,
        transaction_date: form.transaction_date,
        payment_method: form.payment_method || null,
        reference_number: form.reference_number || null,
        description: form.description,
      };
      if (type === "disbursement") {
        payload.payee_name = form.payee_name || null;
        payload.payee_type = form.payee_type || null;
      }
      if (type === "adjustment") {
        payload.adjustment_direction = form.adjustment_direction;
        payload.adjustment_reason = form.adjustment_reason;
      }
      const created = await apiRequest("/api/v1/trust/transactions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      closeModal();
      await loadData(form.currency);
      if (created.receipt_id) {
        setSelectedReceipt(await apiRequest(`/api/v1/trust/receipts/${created.receipt_id}`));
        setModal("receipt");
      }
    } catch (err) {
      setFormError(err.message || "Unable to save trust transaction.");
    } finally {
      setSaving(false);
    }
  }

  async function openReceipt(receiptId) {
    setFormError("");
    try {
      const receipt = await apiRequest(`/api/v1/trust/receipts/${receiptId}`);
      setSelectedReceipt(receipt);
      setModal("receipt");
    } catch (err) {
      setFormError(err.message || "Unable to load trust receipt.");
    }
  }

  async function submitVoid(event) {
    event.preventDefault();
    if (!selectedTransaction) return;
    setSaving(true);
    setFormError("");
    try {
      await apiRequest(`/api/v1/trust/transactions/${selectedTransaction.id}/void`, {
        method: "POST",
        body: JSON.stringify({ void_reason: voidReason }),
      });
      closeModal();
      await loadData(currency);
    } catch (err) {
      setFormError(err.message || "Unable to void trust transaction.");
    } finally {
      setSaving(false);
    }
  }

  if (unauthorized) {
    return (
      <section className="dashboard-page-stack">
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">You are not authorized to view trust accounting.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="dashboard-page-stack trust-finance-page">
      <div className="trust-page__top">
        <div className="dashboard-page-heading">
          <h1>Trust Accounting</h1>
          <p className="trust-page__intro">
            Client funds in trust remain separate from firm operating funds and are never treated as revenue until earned on invoice application.
          </p>
        </div>
        <div className="trust-page__actions">
          {canManage ? (
            <>
              <button type="button" className="vilo-btn vilo-btn--primary" onClick={() => openTransactionModal("deposit")}>Record Trust Deposit</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => openTransactionModal("disbursement")}>Record Disbursement</button>
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={() => openTransactionModal("refund")}>Issue Refund</button>
              <button type="button" className="vilo-btn vilo-btn--ghost" onClick={() => openTransactionModal("adjustment")}>Record Adjustment</button>
            </>
          ) : null}
        </div>
      </div>

      <article className="dashboard-card trust-compliance-banner">
        <strong>Compliance note</strong>
        <span>Trust balances are client funds. They are excluded from firm revenue, profit, and GCT/tax totals until transferred to operating through invoice application.</span>
      </article>

      {error ? (
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">{error}</p>
        </div>
      ) : null}

      <div className="trust-summary-grid trust-summary-grid--three">
        <article className="dashboard-card trust-stat-card">
          <div>
            <p>Total Trust Balance</p>
            <strong>{formatMoney(summaryTotals.totalTrustBalance, currency)}</strong>
          </div>
          <span className="trust-stat-card__meta">{currency}</span>
        </article>
        <article className="dashboard-card trust-stat-card">
          <div>
            <p>Client Ledger Total</p>
            <strong>{formatMoney(summaryTotals.clientTotal, currency)}</strong>
          </div>
          <span className="trust-stat-card__meta">{filteredClientLedgers.length} clients</span>
        </article>
        <article className="dashboard-card trust-stat-card">
          <div>
            <p>Matter Ledger Total</p>
            <strong>{formatMoney(summaryTotals.matterTotal, currency)}</strong>
          </div>
          <span className="trust-stat-card__meta">{filteredMatterLedgers.length} matters</span>
        </article>
      </div>

      <div className="trust-summary-strip">
        <span>Currency: {currency}</span>
        {balances?.client_balance !== null && balances?.client_balance !== undefined ? <span>Client balance snapshot {formatMoney(balances.client_balance, currency)}</span> : null}
        {balances?.matter_balance !== null && balances?.matter_balance !== undefined ? <span>Matter balance snapshot {formatMoney(balances.matter_balance, currency)}</span> : null}
        {queryClientId ? <span>Filtered to client #{queryClientId}</span> : null}
        {queryCaseId ? <span>Filtered to matter #{queryCaseId}</span> : null}
        {refreshing ? <span className="is-good">Refreshing...</span> : null}
      </div>

      <article className="dashboard-card trust-shell-card">
        <div className="trust-toolbar trust-toolbar--finance">
          <div className="trust-filter-group">
            <label className="trust-filter-field">
              <span>Currency</span>
              <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                {availableCurrencies.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="trust-toggle">
              <input type="checkbox" checked={includeVoided} onChange={(event) => setIncludeVoided(event.target.checked)} />
              <span>Include voided</span>
            </label>
          </div>
          <div className="trust-tab-row" role="tablist" aria-label="Trust sections">
            {TAB_OPTIONS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={activeTab === tab ? "trust-tab is-active" : "trust-tab"}
                onClick={() => setActiveTab(tab)}
              >
                {tab.replaceAll("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {loading ? <EmptyState message="Loading trust accounting..." /> : null}

        {!loading && activeTab === "transactions" ? (
          <>
            {!filteredTransactions.length ? <EmptyState message="No trust transactions found for the current filters." /> : (
              <div className="vilo-table-wrap">
                <table className="team-table trust-ledger-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Client</th>
                      <th>Matter</th>
                      <th>Description</th>
                      <th>Payee / Ref</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTransactions.map((txn) => (
                      <tr key={txn.id} className={`trust-ledger-table__row trust-ledger-table__row--${txStatus(txn)}`}>
                        <td>{formatDate(txn.transaction_date)}</td>
                        <td className="trust-ledger-table__type-cell">
                          <span className={`trust-money-pill trust-money-pill--${txDirection(txn)}`}>{txTypeLabel(txn)}</span>
                        </td>
                        <td>{clientById[Number(txn.client_id)]?.name || `Client #${txn.client_id}`}</td>
                        <td>{caseById[Number(txn.case_id)]?.title || `Matter #${txn.case_id}`}</td>
                        <td>{txn.description || "-"}</td>
                        <td>{txn.payee_name || txn.reference_number || "-"}</td>
                        <td className={txDirection(txn) === "outflow" ? "trust-amount trust-amount--outflow" : "trust-amount trust-amount--inflow"}>
                          {txDirection(txn) === "outflow" ? "-" : "+"}
                          {formatMoney(txn.amount, txn.currency)}
                        </td>
                        <td><span className={`vilo-badge trust-status-badge trust-status-badge--${txStatus(txn)}`}>{txStatus(txn)}</span></td>
                        <td>
                          <div className="vilo-table-actions trust-history-actions">
                            {txn.receipt_id ? (
                              <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => openReceipt(txn.receipt_id)}>
                                View receipt
                              </button>
                            ) : null}
                            {canManage && !txn.voided_at && !txn.reversal_of_id ? (
                              <button
                                type="button"
                                className="vilo-btn vilo-btn--secondary vilo-btn--xs"
                                onClick={() => {
                                  setSelectedTransaction(txn);
                                  setVoidReason("");
                                  setFormError("");
                                  setModal("void");
                                }}
                              >
                                Void
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}

        {!loading && activeTab === "client_ledgers" ? (
          !filteredClientLedgers.length ? <EmptyState message="No client trust balances yet." /> : (
            <div className="vilo-table-wrap">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Currency</th>
                    <th>Trust Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredClientLedgers.map((row) => (
                    <tr key={`${row.client_id}-${row.currency}`}>
                      <td>{row.client_name}</td>
                      <td>{row.currency}</td>
                      <td>{formatMoney(row.balance, row.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}

        {!loading && activeTab === "matter_ledgers" ? (
          !filteredMatterLedgers.length ? <EmptyState message="No matter trust balances yet." /> : (
            <div className="vilo-table-wrap">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Matter</th>
                    <th>Client</th>
                    <th>Currency</th>
                    <th>Trust Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMatterLedgers.map((row) => (
                    <tr key={`${row.case_id}-${row.currency}`}>
                      <td>{row.case_title}</td>
                      <td>{row.client_name}</td>
                      <td>{row.currency}</td>
                      <td>{formatMoney(row.balance, row.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}

        {!loading && activeTab === "receipts" ? (
          !depositReceipts.length ? <EmptyState message="No trust receipts have been issued yet." /> : (
            <div className="vilo-table-wrap">
              <table className="team-table">
                <thead>
                  <tr>
                    <th>Receipt</th>
                    <th>Client</th>
                    <th>Matter</th>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {depositReceipts.map((txn) => (
                    <tr key={`receipt-${txn.id}`}>
                      <td>Receipt #{txn.receipt_id}</td>
                      <td>{clientById[Number(txn.client_id)]?.name || `Client #${txn.client_id}`}</td>
                      <td>{caseById[Number(txn.case_id)]?.title || `Matter #${txn.case_id}`}</td>
                      <td>{formatDate(txn.transaction_date)}</td>
                      <td>{formatMoney(txn.amount, txn.currency)}</td>
                      <td><span className={`vilo-badge trust-status-badge trust-status-badge--${txStatus(txn)}`}>{txStatus(txn)}</span></td>
                      <td>
                        <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => openReceipt(txn.receipt_id)}>
                          View receipt
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : null}

        {!loading && activeTab === "reconciliation" ? (
          <div className="trust-placeholder-card">
            <strong>Three-way reconciliation</strong>
            <p>This phase prepares trust ledgers, balances, and receipt history. Reconciliation workflow UI will land in the next finance phase.</p>
          </div>
        ) : null}
      </article>

      {["deposit", "disbursement", "refund", "adjustment"].includes(modal) ? (
        <Modal title={modal === "deposit" ? "Record Trust Deposit" : modal === "disbursement" ? "Record Disbursement" : modal === "refund" ? "Issue Refund" : "Record Adjustment"} copy={sectionCopy(modal)} onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={(event) => submitTransaction(event, modal)}>
            <div className="vilo-form-row-two">
              <select value={forms[modal].trust_account_id} onChange={(event) => updateForm(modal, "trust_account_id", event.target.value)} required>
                <option value="">Trust account</option>
                {accounts.filter((row) => row.currency === forms[modal].currency).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
              <select value={forms[modal].client_id} onChange={(event) => updateForm(modal, "client_id", event.target.value)} required>
                <option value="">Client</option>
                {clients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </div>
            <div className="vilo-form-row-two">
              <select value={forms[modal].case_id} onChange={(event) => updateForm(modal, "case_id", event.target.value)} required>
                <option value="">Matter / case</option>
                {filteredCases
                  .filter((row) => !forms[modal].client_id || Number(row.client_id) === Number(forms[modal].client_id))
                  .map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
              </select>
              <input type="number" step="0.01" min="0" placeholder="Amount" value={forms[modal].amount} onChange={(event) => updateForm(modal, "amount", event.target.value)} required />
            </div>
            <div className="vilo-form-row-two">
              <select value={forms[modal].currency} onChange={(event) => updateForm(modal, "currency", event.target.value)} required>
                {availableCurrencies.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
              <input type="date" value={forms[modal].transaction_date} onChange={(event) => updateForm(modal, "transaction_date", event.target.value)} required />
            </div>
            {modal === "disbursement" ? (
              <div className="vilo-form-row-two">
                <input placeholder="Payee name" value={forms[modal].payee_name} onChange={(event) => updateForm(modal, "payee_name", event.target.value)} required />
                <input placeholder="Payee type" value={forms[modal].payee_type} onChange={(event) => updateForm(modal, "payee_type", event.target.value)} />
              </div>
            ) : null}
            {modal === "adjustment" ? (
              <>
                <div className="vilo-form-row-two">
                  <select value={forms[modal].adjustment_direction} onChange={(event) => updateForm(modal, "adjustment_direction", event.target.value)} required>
                    <option value="increase">Increase</option>
                    <option value="decrease">Decrease</option>
                  </select>
                  <input placeholder="Adjustment reason" value={forms[modal].adjustment_reason} onChange={(event) => updateForm(modal, "adjustment_reason", event.target.value)} required />
                </div>
                <p className="trust-form-warning">Adjustment is an audited correction entry. It does not edit or replace an earlier trust transaction.</p>
              </>
            ) : null}
            <div className="vilo-form-row-two">
              <input placeholder="Payment method" value={forms[modal].payment_method} onChange={(event) => updateForm(modal, "payment_method", event.target.value)} />
              <input placeholder="Reference number" value={forms[modal].reference_number} onChange={(event) => updateForm(modal, "reference_number", event.target.value)} />
            </div>
            <textarea placeholder="Description" value={forms[modal].description} onChange={(event) => updateForm(modal, "description", event.target.value)} required />
            <div className="vilo-table-actions trust-form-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Saving..." : "Submit"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "void" && selectedTransaction ? (
        <Modal title="Void Trust Transaction" copy={sectionCopy("void")} onClose={closeModal}>
          {formError ? <p className="vilo-state vilo-state--error trust-modal__error">{formError}</p> : null}
          <form className="vilo-form-grid" onSubmit={submitVoid}>
            <div className="trust-review-card">
              <strong>{txTypeLabel(selectedTransaction)}</strong>
              <span>{formatMoney(selectedTransaction.amount, selectedTransaction.currency)} on {formatDate(selectedTransaction.transaction_date)}</span>
              <span>{selectedTransaction.description || "No description"}</span>
            </div>
            <textarea placeholder="Void reason" value={voidReason} onChange={(event) => setVoidReason(event.target.value)} required />
            <div className="vilo-table-actions trust-form-actions">
              <button type="button" className="vilo-btn vilo-btn--secondary" onClick={closeModal}>Cancel</button>
              <button type="submit" className="vilo-btn vilo-btn--primary" disabled={saving}>{saving ? "Voiding..." : "Void transaction"}</button>
            </div>
          </form>
        </Modal>
      ) : null}

      {modal === "receipt" && selectedReceipt ? (
        <Modal title={`Trust Receipt ${selectedReceipt.receipt_number}`} copy="Receipt metadata is preserved as part of the trust audit trail." onClose={closeModal}>
          <div className="trust-receipt-grid">
            <p><strong>Client:</strong> {clientById[Number(selectedReceipt.client_id)]?.name || `Client #${selectedReceipt.client_id}`}</p>
            <p><strong>Matter:</strong> {caseById[Number(selectedReceipt.case_id)]?.title || `Matter #${selectedReceipt.case_id}`}</p>
            <p><strong>Date:</strong> {formatDate(selectedReceipt.issued_at)}</p>
            <p><strong>Amount:</strong> {formatMoney(selectedReceipt.amount, selectedReceipt.currency)}</p>
            <p><strong>Payment method:</strong> {selectedReceipt.payment_method || "-"}</p>
            <p><strong>Description:</strong> {selectedReceipt.description || "-"}</p>
            <p><strong>Status:</strong> {selectedReceipt.voided_at ? "Voided" : "Active"}</p>
            <p><strong>PDF:</strong> {selectedReceipt.pdf_available ? "Available" : "Not generated"}</p>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}

export default function TrustPage() {
  return (
    <Suspense fallback={<section className="dashboard-page-stack"><EmptyState message="Loading trust accounting..." /></section>}>
      <TrustPageInner />
    </Suspense>
  );
}
