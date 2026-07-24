function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function optionalText(value) {
  const normalized = String(value || "").trim();
  return normalized || null;
}

function optionalId(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function normalizeInvoicePayload(form, taxRate = 0) {
  const errors = {};
  const clientId = optionalId(form.client_id);
  const manualClientName = optionalText(form.manual_client_name);

  if (!clientId && !manualClientName) {
    errors.client_id = "Select an existing client or use a manual invoice recipient.";
  } else if (clientId && manualClientName) {
    errors.manual_client_name = "Use either an existing client or a manual recipient, not both.";
  }

  const caseId = optionalId(form.case_id);
  if (manualClientName && caseId) {
    errors.case_id = "Manual invoice recipients cannot be linked to a case.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.issue_date || "")) {
    errors.issue_date = "Enter a valid issue date.";
  }
  if (form.due_date && !/^\d{4}-\d{2}-\d{2}$/.test(form.due_date)) {
    errors.due_date = "Enter a valid due date.";
  } else if (form.due_date && form.issue_date && form.due_date < form.issue_date) {
    errors.due_date = "Due date cannot be before issue date.";
  }

  const lineItems = [];
  let calculatedSubtotal = 0;
  (form.line_items || []).forEach((row, index) => {
    const description = optionalText(row.description);
    if (!row.time_entry_id && !description && !row.quantity && !row.unit_price) return;
    if (!description) errors[`line_items.${index}.description`] = "Description is required.";

    if (row.time_entry_id) {
      const timeEntryId = optionalId(row.time_entry_id);
      if (!timeEntryId) errors[`line_items.${index}.time_entry_id`] = "Select a valid time entry.";
      lineItems.push({
        line_type: row.line_type || "hourly_work",
        description: description || "Time entry",
        time_entry_id: timeEntryId,
      });
      calculatedSubtotal += Number(row.amount || 0);
      return;
    }

    const quantity = Number(row.quantity);
    const unitPrice = Number(row.unit_price);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      errors[`line_items.${index}.quantity`] = "Quantity must be greater than zero.";
    }
    if (!Number.isFinite(unitPrice) || unitPrice <= 0) {
      errors[`line_items.${index}.unit_price`] = "Unit price must be greater than zero.";
    }
    lineItems.push({
      line_type: row.line_type || "legal_fee",
      description: description || "",
      quantity,
      unit_price: unitPrice,
      amount: roundMoney(quantity * unitPrice),
    });
    calculatedSubtotal += Number.isFinite(quantity * unitPrice) ? quantity * unitPrice : 0;
  });

  if (!lineItems.length) errors.line_items = "Add at least one invoice line item.";

  const subtotal = roundMoney(calculatedSubtotal);
  const taxAmount = roundMoney(subtotal * (Number(taxRate || 0) / 100));
  const payload = {
    client_id: clientId,
    manual_client_name: manualClientName,
    case_id: manualClientName ? null : caseId,
    invoice_number: optionalText(form.invoice_number),
    currency: String(form.currency || "JMD").trim().toUpperCase() || "JMD",
    issue_date: form.issue_date || "",
    due_date: form.due_date || null,
    notes: optionalText(form.notes),
    payment_instructions: optionalText(form.payment_instructions),
    payment_account_id: optionalId(form.payment_account_id),
    line_items: lineItems,
    subtotal,
    tax_amount: taxAmount,
    total: roundMoney(subtotal + taxAmount),
  };

  return { payload, errors };
}

export function invoiceErrorsByField(errors) {
  return (errors || []).reduce((result, item) => {
    if (item?.field && item?.message && !result[item.field]) result[item.field] = item.message;
    return result;
  }, {});
}
