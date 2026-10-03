"use client";

import { FormEvent, useState } from "react";

import { ApiError, api as defaultApi, type Api } from "@/lib/api";
import { MSG } from "@/lib/messages";
import type { Cashier } from "@/lib/types";
import { isValidPasswordLength } from "@/lib/validation";

interface Props {
  api?: Api;
  notice?: string | null;
  onSuccess: (cashier: Cashier) => void;
}

/** S-01 ログイン画面のフォーム */
export function LoginForm({ api = defaultApi, notice, onSuccess }: Props) {
  const [cashierId, setCashierId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!isValidPasswordLength(password)) {
      setError(MSG.passwordLength);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.login(cashierId.trim(), password);
      onSuccess(res.cashier);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      if (apiErr?.code === "AUTH_FAILED") setError(MSG.authFailed);
      else setError(apiErr?.message ?? MSG.network);
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login-card" onSubmit={submit} noValidate>
      <h1 className="login-title">レジにログイン</h1>
      {notice && <p className="message message-warn" role="status">{notice}</p>}
      <label className="field">
        <span className="field-label">担当者ID</span>
        <input
          className="input"
          value={cashierId}
          onChange={(e) => setCashierId(e.target.value)}
          autoComplete="username"
          autoFocus
          maxLength={20}
          required
        />
      </label>
      <label className="field">
        <span className="field-label">パスワード</span>
        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          maxLength={64}
          required
        />
      </label>
      {error && <p className="message message-error" role="alert">{error}</p>}
      <button type="submit" className="btn btn-primary btn-block" disabled={busy || !cashierId.trim() || !password}>
        {busy ? "確認しています…" : "ログイン"}
      </button>
    </form>
  );
}
