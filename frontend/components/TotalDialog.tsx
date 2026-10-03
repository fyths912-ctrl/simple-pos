"use client";

import { useEffect, useRef } from "react";

import { formatDateTime, yen } from "@/lib/format";
import type { TransactionResult } from "@/lib/types";

interface Props {
  result: TransactionResult;
  onClose: () => void;
}

/** 合計ポップアップ（F-007／UC-08）。閉じると次のお客様の状態に戻る。 */
export function TotalDialog({ result, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), []);

  return (
    <div className="dialog-backdrop">
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="total-title"
        onKeyDown={(e) => e.key === "Escape" && onClose()}
      >
        <p className="dialog-meta">
          取引ID {result.transaction_id}　{formatDateTime(result.transaction_at)}
        </p>
        <h2 id="total-title" className="dialog-title">お会計が確定しました</h2>
        <dl className="dialog-amounts">
          <div className="dialog-row">
            <dt>税抜合計</dt>
            <dd data-testid="subtotal">{yen(result.subtotal_excl_tax)}</dd>
          </div>
          <div className="dialog-row">
            <dt>消費税</dt>
            <dd data-testid="tax">{yen(result.tax_amount)}</dd>
          </div>
          <div className="dialog-row dialog-total">
            <dt>税込合計</dt>
            <dd data-testid="total">{yen(result.total_incl_tax)}</dd>
          </div>
        </dl>
        <button ref={closeRef} type="button" className="btn btn-primary btn-block" onClick={onClose}>
          閉じて次のお客様へ
        </button>
      </div>
    </div>
  );
}
