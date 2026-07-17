"use client";

import { useCallback, useEffect, useState } from "react";

export function useModalCloseGuard({ open, isDirty, isSubmitting = false, onClose, onDiscard }) {
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  const requestClose = useCallback(() => {
    if (isSubmitting) return;
    if (!isDirty) {
      onClose?.();
      return;
    }
    setConfirmDiscard(true);
  }, [isDirty, isSubmitting, onClose]);

  const keepEditing = useCallback(() => {
    setConfirmDiscard(false);
  }, []);

  const discard = useCallback(() => {
    setConfirmDiscard(false);
    onDiscard?.();
    onClose?.();
  }, [onClose, onDiscard]);

  useEffect(() => {
    if (!open) {
      setConfirmDiscard(false);
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      requestClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, requestClose]);

  return {
    confirmDiscard,
    requestClose,
    keepEditing,
    discard,
  };
}

export function DiscardChangesDialog({ open, onKeepEditing, onDiscard }) {
  if (!open) return null;

  return (
    <div className="vilo-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
      <div className="vilo-modal__header">
        <h3>Discard the information you entered?</h3>
      </div>
      <div className="vilo-modal__body">
        <div className="vilo-table-actions">
          <button className="vilo-btn vilo-btn--secondary" type="button" onClick={onKeepEditing}>Keep editing</button>
          <button className="vilo-btn vilo-btn--primary" type="button" onClick={onDiscard}>Discard</button>
        </div>
      </div>
    </div>
  );
}
