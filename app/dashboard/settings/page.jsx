"use client";

import { useEffect, useMemo, useState } from "react";
import { getCachedUser, setCachedUser } from "../../../lib/auth";
import { apiRequest } from "../../../lib/api";

const SETTINGS_TABS = [
  { id: "firm", label: "Firm Details" },
  { id: "payment_accounts", label: "Payment Accounts" },
  { id: "billing_rates", label: "Billing Rates" },
  { id: "billing_tax", label: "Tax / GCT" },
];

const ROLE_OPTIONS = [
  { value: "partner", label: "Partner" },
  { value: "admin", label: "Admin" },
  { value: "lawyer", label: "Lawyer" },
  { value: "paralegal", label: "Paralegal" },
];

const paymentAccountInitial = {
  account_name: "",
  bank_name: "",
  account_number: "",
  currency: "USD",
  swift_routing: "",
  notes: "",
  payment_instructions: "",
  is_default: false,
};

const billingRateInitial = {
  rate_type: "role",
  role_name: "lawyer",
  user_id: "",
  currency: "USD",
  hourly_rate: "",
  is_active: true,
};

const billingTaxInitial = {
  invoice_tax_label: "GCT",
  invoice_tax_rate: "0.00",
};

function roleCanViewSettings(role) {
  return ["partner", "admin", "lawyer", "paralegal"].includes(role);
}

function roleCanManageSettings(role) {
  return role === "partner" || role === "admin";
}

function formatMoney(value, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value || 0));
}

function normalizeError(err) {
  return err?.message || "Request failed.";
}

function CurrencyBadge({ value }) {
  return <span className="vilo-badge vilo-badge--active">{value}</span>;
}

function DefaultBadge() {
  return <span className="vilo-badge">Default</span>;
}

export default function SettingsPage() {
  const [currentUser, setCurrentUser] = useState(getCachedUser());
  const [activeTab, setActiveTab] = useState("payment_accounts");
  const [paymentAccounts, setPaymentAccounts] = useState([]);
  const [billingRates, setBillingRates] = useState([]);
  const [team, setTeam] = useState([]);
  const [billingTax, setBillingTax] = useState(billingTaxInitial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [unauthorized, setUnauthorized] = useState(false);
  const [savingAccount, setSavingAccount] = useState(false);
  const [savingRate, setSavingRate] = useState(false);
  const [savingTax, setSavingTax] = useState(false);
  const [accountForm, setAccountForm] = useState(paymentAccountInitial);
  const [rateForm, setRateForm] = useState(billingRateInitial);
  const [accountEditingId, setAccountEditingId] = useState(null);
  const [rateEditingId, setRateEditingId] = useState(null);
  const [taxError, setTaxError] = useState("");
  const [taxSuccess, setTaxSuccess] = useState("");
  const [accountError, setAccountError] = useState("");
  const [rateError, setRateError] = useState("");
  const [accountSuccess, setAccountSuccess] = useState("");
  const [rateSuccess, setRateSuccess] = useState("");

  const canManage = roleCanManageSettings(currentUser?.role || "");
  const canView = currentUser ? roleCanViewSettings(currentUser.role) : true;
  const staffUsers = useMemo(() => (team || []).filter((row) => row.role !== "client"), [team]);

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

  useEffect(() => {
    if (currentUser && !roleCanViewSettings(currentUser.role)) {
      setUnauthorized(true);
      setLoading(false);
      return;
    }

    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      setUnauthorized(false);
      try {
        const [accounts, rates, teamRows, taxSettings] = await Promise.all([
          apiRequest("/api/v1/settings/payment-accounts"),
          apiRequest("/api/v1/settings/billing-rates"),
          apiRequest("/api/v1/team").catch(() => []),
          apiRequest("/api/v1/settings/billing-tax").catch(() => billingTaxInitial),
        ]);
        if (cancelled) return;
        setPaymentAccounts(accounts || []);
        setBillingRates(rates || []);
        setTeam((teamRows || []).filter((row) => row.role !== "client"));
        setBillingTax(taxSettings || billingTaxInitial);
      } catch (err) {
        if (cancelled) return;
        const message = normalizeError(err);
        if (message.toLowerCase().includes("insufficient role")) {
          setUnauthorized(true);
        } else {
          setError(message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  function resetAccountForm() {
    setAccountEditingId(null);
    setAccountError("");
    setAccountSuccess("");
    setAccountForm(paymentAccountInitial);
  }

  function resetRateForm() {
    setRateEditingId(null);
    setRateError("");
    setRateSuccess("");
    setRateForm(billingRateInitial);
  }

  function startEditAccount(account) {
    setActiveTab("payment_accounts");
    setAccountEditingId(account.id);
    setAccountError("");
    setAccountSuccess("");
    setAccountForm({
      account_name: account.account_name || "",
      bank_name: account.bank_name || "",
      account_number: account.account_number || "",
      currency: account.currency || "USD",
      swift_routing: account.swift_routing || "",
      notes: account.notes || "",
      payment_instructions: account.payment_instructions || "",
      is_default: Boolean(account.is_default),
    });
  }

  function startEditRate(rate) {
    setActiveTab("billing_rates");
    setRateEditingId(rate.id);
    setRateError("");
    setRateSuccess("");
    setRateForm({
      rate_type: rate.rate_type || "role",
      role_name: rate.role_name || "lawyer",
      user_id: rate.user_id ? String(rate.user_id) : "",
      currency: rate.currency || "USD",
      hourly_rate: String(rate.hourly_rate || ""),
      is_active: Boolean(rate.is_active),
    });
  }

  async function reloadPaymentAccounts() {
    const rows = await apiRequest("/api/v1/settings/payment-accounts");
    setPaymentAccounts(rows || []);
  }

  async function reloadBillingRates() {
    const rows = await apiRequest("/api/v1/settings/billing-rates");
    setBillingRates(rows || []);
  }

  async function reloadBillingTax() {
    const row = await apiRequest("/api/v1/settings/billing-tax");
    setBillingTax(row || billingTaxInitial);
  }

  async function submitPaymentAccount(event) {
    event.preventDefault();
    setSavingAccount(true);
    setAccountError("");
    setAccountSuccess("");
    try {
      const payload = {
        account_name: accountForm.account_name.trim(),
        bank_name: accountForm.bank_name.trim(),
        account_number: accountForm.account_number.trim(),
        currency: accountForm.currency,
        swift_routing: accountForm.swift_routing.trim() || null,
        notes: accountForm.notes.trim() || null,
        payment_instructions: accountForm.payment_instructions.trim() || null,
        is_default: Boolean(accountForm.is_default),
      };
      if (!payload.account_name || !payload.bank_name || !payload.account_number) {
        throw new Error("Account name, bank name, and account number are required.");
      }
      await apiRequest(
        accountEditingId ? `/api/v1/settings/payment-accounts/${accountEditingId}` : "/api/v1/settings/payment-accounts",
        {
          method: accountEditingId ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
      await reloadPaymentAccounts();
      setAccountSuccess(accountEditingId ? "Payment account updated." : "Payment account created.");
      setAccountEditingId(null);
      setAccountForm(paymentAccountInitial);
    } catch (err) {
      setAccountError(normalizeError(err));
    } finally {
      setSavingAccount(false);
    }
  }

  async function submitBillingRate(event) {
    event.preventDefault();
    setSavingRate(true);
    setRateError("");
    setRateSuccess("");
    try {
      const payload = {
        rate_type: rateForm.rate_type,
        role_name: rateForm.rate_type === "role" ? rateForm.role_name : null,
        user_id: rateForm.rate_type === "user_override" && rateForm.user_id ? Number(rateForm.user_id) : null,
        currency: rateForm.currency,
        hourly_rate: Number(rateForm.hourly_rate || 0),
        is_active: Boolean(rateForm.is_active),
      };
      if (!payload.hourly_rate && payload.hourly_rate !== 0) {
        throw new Error("Hourly rate is required.");
      }
      if (rateForm.rate_type === "user_override" && !payload.user_id) {
        throw new Error("Select a staff member for user override.");
      }
      await apiRequest(
        rateEditingId ? `/api/v1/settings/billing-rates/${rateEditingId}` : "/api/v1/settings/billing-rates",
        {
          method: rateEditingId ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
      await reloadBillingRates();
      setRateSuccess(rateEditingId ? "Billing rate updated." : "Billing rate created.");
      setRateEditingId(null);
      setRateForm(billingRateInitial);
    } catch (err) {
      setRateError(normalizeError(err));
    } finally {
      setSavingRate(false);
    }
  }

  async function submitBillingTax(event) {
    event.preventDefault();
    setSavingTax(true);
    setTaxError("");
    setTaxSuccess("");
    try {
      await apiRequest("/api/v1/settings/billing-tax", {
        method: "PATCH",
        body: JSON.stringify({
          invoice_tax_label: billingTax.invoice_tax_label.trim(),
          invoice_tax_rate: Number(billingTax.invoice_tax_rate || 0),
        }),
      });
      await reloadBillingTax();
      setTaxSuccess("Billing tax settings updated.");
    } catch (err) {
      setTaxError(normalizeError(err));
    } finally {
      setSavingTax(false);
    }
  }

  async function setDefaultAccount(accountId) {
    setAccountError("");
    setAccountSuccess("");
    try {
      await apiRequest(`/api/v1/settings/payment-accounts/${accountId}/set-default`, { method: "POST" });
      await reloadPaymentAccounts();
      setAccountSuccess("Default payment account updated.");
    } catch (err) {
      setAccountError(normalizeError(err));
    }
  }

  async function deactivateAccount(accountId) {
    setAccountError("");
    setAccountSuccess("");
    try {
      await apiRequest(`/api/v1/settings/payment-accounts/${accountId}`, { method: "DELETE" });
      await reloadPaymentAccounts();
      setAccountSuccess("Payment account deactivated.");
      if (accountEditingId === accountId) resetAccountForm();
    } catch (err) {
      setAccountError(normalizeError(err));
    }
  }

  async function deactivateRate(rateId) {
    setRateError("");
    setRateSuccess("");
    try {
      await apiRequest(`/api/v1/settings/billing-rates/${rateId}`, { method: "DELETE" });
      await reloadBillingRates();
      setRateSuccess("Billing rate deactivated.");
      if (rateEditingId === rateId) resetRateForm();
    } catch (err) {
      setRateError(normalizeError(err));
    }
  }

  if (unauthorized || (currentUser && !canView)) {
    return (
      <section className="dashboard-page-stack">
        <div className="vilo-state-block">
          <p className="vilo-state vilo-state--error">You are not authorized to view billing settings.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="dashboard-page-stack settings-page">
      <div className="dashboard-page-heading">
        <h1>Settings</h1>
        <p className="invoice-page-intro">Configure invoice display accounts and billing rates without changing trust or accounting logic.</p>
      </div>

      <article className="dashboard-card settings-banner">
        <strong>Compliance note</strong>
        <span>Payment accounts are displayed on invoices only. They do not affect accounting logic.</span>
      </article>

      <article className="dashboard-card settings-tabs-card">
        <div className="settings-tabs" role="tablist" aria-label="Settings tabs">
          {SETTINGS_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={activeTab === tab.id ? "settings-tab is-active" : "settings-tab"}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </article>

      {error ? <div className="vilo-state-block"><p className="vilo-state vilo-state--error">{error}</p></div> : null}
      {loading ? <div className="vilo-state-block"><p className="vilo-state vilo-state--loading">Loading settings...</p></div> : null}

      {!loading && activeTab === "firm" ? (
        <div className="settings-grid">
          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header"><h2>Firm Details</h2></div>
            <p className="vilo-card-copy">Firm payment and billing controls now live in the tabs beside this one. Existing organization profile details remain unchanged.</p>
            <ul className="settings-bullet-list">
              <li>Payment accounts are invoice display and payment-instruction data only.</li>
              <li>Billing rates apply to time entries, invoicing, and staff reports only.</li>
              <li>Neither setting affects trust accounting or trust balances.</li>
            </ul>
          </article>
        </div>
      ) : null}

      {!loading && activeTab === "payment_accounts" ? (
        <div className="settings-grid">
          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header">
              <div>
                <h2>Payment Accounts</h2>
                <p className="settings-copy">Payment accounts are displayed on invoices only. They do not affect accounting logic.</p>
              </div>
            </div>

            {paymentAccounts.length ? (
              <div className="vilo-table-wrap">
                <table className="team-table">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th>Currency</th>
                      <th>Status</th>
                      <th>Instructions</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paymentAccounts.map((account) => (
                      <tr key={account.id}>
                        <td>
                          <div className="settings-row-stack">
                            <strong>{account.account_name}</strong>
                            <span>{account.bank_name}</span>
                            <span>{account.account_number}</span>
                          </div>
                        </td>
                        <td><CurrencyBadge value={account.currency} /></td>
                        <td>
                          <div className="settings-row-badges">
                            {account.is_default ? <DefaultBadge /> : null}
                            <span className={account.is_active ? "vilo-badge vilo-badge--active" : "vilo-badge"}>{account.is_active ? "Active" : "Inactive"}</span>
                          </div>
                        </td>
                        <td>{account.payment_instructions || account.notes || "-"}</td>
                        <td>
                          <div className="vilo-table-actions">
                            <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => startEditAccount(account)}>View</button>
                            {canManage ? (
                              <>
                                {!account.is_default && account.is_active ? <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => setDefaultAccount(account.id)}>Set default</button> : null}
                                {account.is_active ? <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => deactivateAccount(account.id)}>Deactivate</button> : null}
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="vilo-state-block">
                <p className="vilo-state">No payment accounts configured yet.</p>
              </div>
            )}
          </article>

          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header">
              <div>
                <h2>{accountEditingId ? "Edit Payment Account" : "Add Payment Account"}</h2>
                <p className="settings-copy">{canManage ? "Manage invoice payment instructions by currency." : "You can review configured payment accounts, but management is limited to partner/admin roles."}</p>
              </div>
            </div>

            {accountError ? <p className="vilo-state vilo-state--error">{accountError}</p> : null}
            {accountSuccess ? <p className="vilo-state">{accountSuccess}</p> : null}

            <form className="settings-form" onSubmit={submitPaymentAccount}>
              <div className="vilo-form-row-two">
                <div>
                  <label>Account Name</label>
                  <input value={accountForm.account_name} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, account_name: event.target.value }))} />
                </div>
                <div>
                  <label>Bank Name</label>
                  <input value={accountForm.bank_name} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, bank_name: event.target.value }))} />
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>Account Number</label>
                  <input value={accountForm.account_number} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, account_number: event.target.value }))} />
                </div>
                <div>
                  <label>Currency</label>
                  <select value={accountForm.currency} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, currency: event.target.value }))}>
                    <option value="USD">USD</option>
                    <option value="JMD">JMD</option>
                  </select>
                </div>
              </div>

              <div className="vilo-form-row-two">
                <div>
                  <label>SWIFT / Routing</label>
                  <input value={accountForm.swift_routing} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, swift_routing: event.target.value }))} />
                </div>
                <div className="settings-checkbox-field">
                  <label>
                    <input type="checkbox" checked={accountForm.is_default} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, is_default: event.target.checked }))} />
                    Default account for this currency
                  </label>
                </div>
              </div>

              <div>
                <label>Payment Instructions</label>
                <textarea value={accountForm.payment_instructions} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, payment_instructions: event.target.value }))} placeholder="Wire instructions, branch details, collection notes..." />
              </div>

              <div>
                <label>Notes</label>
                <textarea value={accountForm.notes} disabled={!canManage} onChange={(event) => setAccountForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Optional internal reference notes" />
              </div>

              {canManage ? (
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={resetAccountForm}>Reset</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={savingAccount}>{savingAccount ? "Saving..." : accountEditingId ? "Save payment account" : "Add payment account"}</button>
                </div>
              ) : (
                <div className="vilo-state-block">
                  <p className="vilo-state">View only. Partner/admin roles can add, edit, set default, or deactivate accounts.</p>
                </div>
              )}
            </form>
          </article>
        </div>
      ) : null}

      {!loading && activeTab === "billing_rates" ? (
        <div className="settings-grid">
          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header">
              <div>
                <h2>Billing Rates</h2>
                <p className="settings-copy">Billing rates apply to time entries and invoicing only. They do not affect trust accounting.</p>
              </div>
            </div>

            <article className="settings-info-banner">
              <strong>Rate precedence</strong>
              <span>User override rate takes precedence over role rate.</span>
            </article>

            {billingRates.length ? (
              <div className="vilo-table-wrap">
                <table className="team-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Role / User</th>
                      <th>Currency</th>
                      <th>Hourly Rate</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {billingRates.map((rate) => {
                      const linkedUser = staffUsers.find((user) => Number(user.id) === Number(rate.user_id));
                      return (
                        <tr key={rate.id}>
                          <td>{rate.rate_type === "user_override" ? "User Override" : "Role-Based"}</td>
                          <td>{rate.rate_type === "user_override" ? (linkedUser ? `${linkedUser.name} (${linkedUser.role})` : `User #${rate.user_id}`) : rate.role_name}</td>
                          <td><CurrencyBadge value={rate.currency} /></td>
                          <td>{formatMoney(rate.hourly_rate, rate.currency)}</td>
                          <td><span className={rate.is_active ? "vilo-badge vilo-badge--active" : "vilo-badge"}>{rate.is_active ? "Active" : "Inactive"}</span></td>
                          <td>
                            <div className="vilo-table-actions">
                              <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={() => startEditRate(rate)}>View</button>
                              {canManage && rate.is_active ? <button type="button" className="vilo-btn vilo-btn--ghost vilo-btn--xs" onClick={() => deactivateRate(rate.id)}>Deactivate</button> : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="vilo-state-block">
                <p className="vilo-state">No billing rates configured yet.</p>
              </div>
            )}
          </article>

          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header">
              <div>
                <h2>{rateEditingId ? "Edit Billing Rate" : "Add Billing Rate"}</h2>
                <p className="settings-copy">Configure role-based defaults or individual user overrides by currency.</p>
              </div>
            </div>

            {rateError ? <p className="vilo-state vilo-state--error">{rateError}</p> : null}
            {rateSuccess ? <p className="vilo-state">{rateSuccess}</p> : null}

            <form className="settings-form" onSubmit={submitBillingRate}>
              <div className="vilo-form-row-two">
                <div>
                  <label>Rate Type</label>
                  <select value={rateForm.rate_type} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, rate_type: event.target.value, user_id: "", role_name: "lawyer" }))}>
                    <option value="role">Role-Based</option>
                    <option value="user_override">User Override</option>
                  </select>
                </div>
                <div>
                  <label>Currency</label>
                  <select value={rateForm.currency} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, currency: event.target.value }))}>
                    <option value="USD">USD</option>
                    <option value="JMD">JMD</option>
                  </select>
                </div>
              </div>

              {rateForm.rate_type === "role" ? (
                <div>
                  <label>Role</label>
                  <select value={rateForm.role_name} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, role_name: event.target.value }))}>
                    {ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
              ) : (
                <div>
                  <label>Staff Member</label>
                  <select value={rateForm.user_id} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, user_id: event.target.value }))}>
                    <option value="">Select staff member</option>
                    {staffUsers.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.role})</option>)}
                  </select>
                  {!staffUsers.length ? <p className="settings-helper-text">No staff users found for overrides.</p> : null}
                </div>
              )}

              <div className="vilo-form-row-two">
                <div>
                  <label>Hourly Rate</label>
                  <input type="number" min="0" step="0.01" value={rateForm.hourly_rate} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, hourly_rate: event.target.value }))} placeholder="0.00" />
                </div>
                <div className="settings-checkbox-field">
                  <label>
                    <input type="checkbox" checked={rateForm.is_active} disabled={!canManage} onChange={(event) => setRateForm((current) => ({ ...current, is_active: event.target.checked }))} />
                    Active rate
                  </label>
                </div>
              </div>

              {canManage ? (
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={resetRateForm}>Reset</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={savingRate}>{savingRate ? "Saving..." : rateEditingId ? "Save billing rate" : "Add billing rate"}</button>
                </div>
              ) : (
                <div className="vilo-state-block">
                  <p className="vilo-state">View only. Partner/admin roles can manage billing rates.</p>
                </div>
              )}
            </form>
          </article>
        </div>
      ) : null}

      {!loading && activeTab === "billing_tax" ? (
        <div className="settings-grid">
          <article className="dashboard-card settings-card">
            <div className="dashboard-card__header">
              <div>
                <h2>Invoice Tax / GCT</h2>
                <p className="settings-copy">This firm-level setting auto-applies to invoices. Trust deposits, escrow, and client funds remain excluded.</p>
              </div>
            </div>

            <article className="settings-info-banner">
              <strong>Billing control</strong>
              <span>Invoice tax percentage is managed here only. Invoice creators can review the applied rate but cannot enter a manual percentage.</span>
            </article>

            {taxError ? <p className="vilo-state vilo-state--error">{taxError}</p> : null}
            {taxSuccess ? <p className="vilo-state">{taxSuccess}</p> : null}

            <form className="settings-form" onSubmit={submitBillingTax}>
              <div className="vilo-form-row-two">
                <div>
                  <label>Tax Label</label>
                  <input value={billingTax.invoice_tax_label} disabled={!canManage} onChange={(event) => setBillingTax((current) => ({ ...current, invoice_tax_label: event.target.value }))} />
                </div>
                <div>
                  <label>Tax Percentage</label>
                  <input type="number" min="0" step="0.01" value={billingTax.invoice_tax_rate} disabled={!canManage} onChange={(event) => setBillingTax((current) => ({ ...current, invoice_tax_rate: event.target.value }))} />
                </div>
              </div>

              {canManage ? (
                <div className="vilo-table-actions">
                  <button type="button" className="vilo-btn vilo-btn--secondary" onClick={reloadBillingTax}>Reset</button>
                  <button type="submit" className="vilo-btn vilo-btn--primary" disabled={savingTax}>{savingTax ? "Saving..." : "Save tax settings"}</button>
                </div>
              ) : (
                <div className="vilo-state-block">
                  <p className="vilo-state">View only. Partner/admin roles can update firm billing tax settings.</p>
                </div>
              )}
            </form>
          </article>
        </div>
      ) : null}
    </section>
  );
}
