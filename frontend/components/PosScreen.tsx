"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, api as defaultApi, type Api } from "@/lib/api";
import { addToCart, cartCount, cartSubtotal, changeQuantity, lineSubtotal, removeFromCart } from "@/lib/cart";
import { newIdempotencyKey, yen } from "@/lib/format";
import { MSG } from "@/lib/messages";
import type { CartItem, Cashier, Product, SalesMode, TransactionResult } from "@/lib/types";
import { isValidMemberId, isValidProductCode, normalizeMemberId, normalizeProductCode } from "@/lib/validation";

import { TotalDialog } from "./TotalDialog";

type Customer = { kind: "pending" } | { kind: "member"; id: string; name: string } | { kind: "guest" };

interface Props {
  cashier: Cashier;
  api?: Api;
  onSessionExpired: () => void;
  onLogout: () => void;
}

const SALES_MODES: { value: SalesMode; label: string; note: string }[] = [
  { value: "DINE_IN", label: "店内", note: "店内でお召し上がり" },
  { value: "TAKEOUT", label: "持ち帰り", note: "テイクアウト" },
];

/** S-02 POSメイン画面 */
export function PosScreen({ cashier, api = defaultApi, onSessionExpired, onLogout }: Props) {
  const [customer, setCustomer] = useState<Customer>({ kind: "pending" });
  const [memberInput, setMemberInput] = useState("");
  const [memberError, setMemberError] = useState<string | null>(null);
  const [memberLoading, setMemberLoading] = useState(false);

  const [salesMode, setSalesMode] = useState<SalesMode | null>(null);

  const [codeInput, setCodeInput] = useState("");
  const [found, setFound] = useState<Product | null>(null);
  const [productError, setProductError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const [cart, setCart] = useState<CartItem[]>([]);
  const [cartNotice, setCartNotice] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<TransactionResult | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey);
  const inFlight = useRef(false);

  const memberRef = useRef<HTMLInputElement>(null);
  const codeRef = useRef<HTMLInputElement>(null);

  const memberId = customer.kind === "member" ? customer.id : null;
  const customerReady = customer.kind !== "pending";

  // 会計の中身が変わったら新しいキーにする。中身が同じままの再送（失敗後の再試行・連打）は同じキー
  useEffect(() => setIdempotencyKey(newIdempotencyKey()), [cart, salesMode, memberId]);

  useEffect(() => {
    if (customerReady) codeRef.current?.focus();
    else memberRef.current?.focus();
  }, [customerReady]);

  function handleApiError(e: unknown): ApiError | null {
    if (e instanceof ApiError && e.status === 401) {
      onSessionExpired(); // 入力中の内容は破棄し、ログイン画面へ（設計9.1）
      return null;
    }
    return e instanceof ApiError ? e : new ApiError(0, "UNKNOWN", MSG.network);
  }

  // ---- お客様 ----
  async function lookupMember(e: FormEvent) {
    e.preventDefault();
    const id = normalizeMemberId(memberInput);
    setMemberInput(id);
    if (!isValidMemberId(id)) {
      setMemberError(MSG.memberIdFormat);
      return;
    }
    setMemberLoading(true);
    setMemberError(null);
    try {
      const m = await api.getMember(id);
      setCustomer({ kind: "member", id: m.member_id, name: m.display_name });
    } catch (err) {
      const apiErr = handleApiError(err);
      if (apiErr) setMemberError(apiErr.code === "MEMBER_NOT_FOUND" ? MSG.memberNotFound : apiErr.message);
    } finally {
      setMemberLoading(false);
    }
  }

  function startAsGuest() {
    setMemberError(null);
    setMemberInput("");
    setCustomer({ kind: "guest" });
  }

  // ---- 商品 ----
  async function searchProduct(e: FormEvent) {
    e.preventDefault();
    const code = normalizeProductCode(codeInput);
    setCodeInput(code);
    setFound(null);
    setCartNotice(null);
    if (!isValidProductCode(code)) {
      setProductError(MSG.productCodeFormat);
      return;
    }
    setSearching(true);
    setProductError(null);
    try {
      setFound(await api.getProduct(code));
    } catch (err) {
      const apiErr = handleApiError(err);
      if (apiErr) setProductError(apiErr.code === "PRODUCT_NOT_FOUND" ? MSG.productNotFound : apiErr.message);
    } finally {
      setSearching(false);
    }
  }

  function addFound() {
    if (!found) return; // 検索結果がなければ追加しない（T-024）
    const next = addToCart(cart, found);
    setCart(next.items);
    setCartNotice(next.capped ? MSG.quantityCap : null);
    setSubmitError(null);
    // 追加後は入力欄・名称・単価をクリアして次の商品へ（F-002／T-026）
    setCodeInput("");
    setFound(null);
    setProductError(null);
    codeRef.current?.focus();
  }

  // ---- 購入確定 ----
  const canConfirm = customerReady && cart.length > 0 && salesMode !== null && !submitting;

  async function confirmPurchase() {
    if (inFlight.current) return; // 連打対策（同じ描画中の2回目のクリックを無視）
    if (cart.length === 0) return setSubmitError(MSG.emptyCart);
    if (!salesMode) return setSubmitError(MSG.salesModeRequired);
    inFlight.current = true;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await api.createTransaction({
        member_id: memberId,
        sales_mode: salesMode,
        idempotency_key: idempotencyKey,
        items: cart.map((i) => ({ product_code: i.productCode, quantity: i.quantity })),
      });
      setResult(res);
    } catch (err) {
      const apiErr = handleApiError(err);
      if (apiErr) {
        const byCode: Record<string, string> = {
          EMPTY_CART: MSG.emptyCart,
          MEMBER_NOT_FOUND: MSG.memberNotFound,
          PRODUCT_CHANGED_OR_NOT_FOUND: MSG.productChanged,
          VALIDATION_ERROR: apiErr.message,
          TAX_RATE_NOT_CONFIGURED: apiErr.message,
        };
        // 保存失敗時は購入リストを残す（設計12.1）
        setSubmitError(byCode[apiErr.code] ?? MSG.saveFailed);
      }
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  function nextCustomer() {
    setResult(null);
    setCustomer({ kind: "pending" });
    setMemberInput("");
    setMemberError(null);
    setSalesMode(null);
    setCodeInput("");
    setFound(null);
    setProductError(null);
    setCart([]);
    setCartNotice(null);
    setSubmitError(null);
  }

  const confirmHint =
    !customerReady ? "お客様を選ぶと会計できます" :
    cart.length === 0 ? MSG.emptyCart :
    salesMode === null ? MSG.salesModeRequired : null;

  return (
    <div className="pos">
      <header className="pos-header">
        <span className="pos-brand">お会計</span>
        <span className="pos-cashier" data-testid="cashier">
          担当 {cashier.cashier_name}（{cashier.cashier_id}）
        </span>
        <button type="button" className="btn btn-quiet" onClick={onLogout}>ログアウト</button>
      </header>

      <main className="pos-main">
        <div className="pos-steps">
          {/* お客様 */}
          <section className="step" aria-labelledby="h-customer">
            <h2 id="h-customer" className="step-title">お客様</h2>
            {customer.kind === "pending" ? (
              <>
                <form className="field-row" onSubmit={lookupMember}>
                  <label className="field">
                    <span className="field-label">会員ID</span>
                    <input
                      ref={memberRef}
                      className="input"
                      value={memberInput}
                      onChange={(e) => setMemberInput(e.target.value)}
                      placeholder="M000123"
                      autoComplete="off"
                      maxLength={12}
                      aria-invalid={memberError ? true : undefined}
                      aria-describedby={memberError ? "member-error" : undefined}
                    />
                  </label>
                  <button type="submit" className="btn btn-secondary" disabled={memberLoading || !memberInput.trim()}>
                    会員を読み込む
                  </button>
                </form>
                {memberError && <p id="member-error" className="message message-error" role="alert">{memberError}</p>}
                <button type="button" className="btn btn-outline btn-block" onClick={startAsGuest}>
                  非会員として開始
                </button>
              </>
            ) : (
              <div className="customer-chip">
                <div>
                  <span className="customer-kind">{customer.kind === "member" ? `会員 ${customer.id}` : "非会員"}</span>
                  {customer.kind === "member" && (
                    <span className="customer-name" data-testid="member-name">{customer.name} 様</span>
                  )}
                </div>
                <button type="button" className="btn btn-quiet" onClick={() => setCustomer({ kind: "pending" })}>
                  変更
                </button>
              </div>
            )}
          </section>

          {/* 取引区分 */}
          <section className="step" aria-labelledby="h-mode">
            <h2 id="h-mode" className="step-title">取引区分</h2>
            <div className="mode-group" role="radiogroup" aria-labelledby="h-mode">
              {SALES_MODES.map((m) => (
                <label key={m.value} className={`mode mode-${m.value.toLowerCase()}`}>
                  <input
                    type="radio"
                    name="sales-mode"
                    value={m.value}
                    checked={salesMode === m.value}
                    onChange={() => setSalesMode(m.value)}
                  />
                  <span className="mode-label">{m.label}</span>
                  <span className="mode-note">{m.note}</span>
                </label>
              ))}
            </div>
          </section>

          {/* 商品 */}
          <section className="step" aria-labelledby="h-product">
            <h2 id="h-product" className="step-title">商品</h2>
            <fieldset className="plain-fieldset" disabled={!customerReady}>
              {!customerReady && <p className="message">先にお客様（会員／非会員）を選んでください。</p>}
              <form className="field-row" onSubmit={searchProduct}>
                <label className="field">
                  <span className="field-label">商品コード</span>
                  <input
                    ref={codeRef}
                    className="input input-code"
                    value={codeInput}
                    onChange={(e) => setCodeInput(e.target.value)}
                    inputMode="numeric"
                    autoComplete="off"
                    maxLength={20}
                    placeholder="13桁"
                    aria-invalid={productError ? true : undefined}
                    aria-describedby={productError ? "product-error" : undefined}
                  />
                </label>
                <button type="submit" className="btn btn-secondary" disabled={searching || !codeInput.trim()}>
                  読み込み
                </button>
              </form>
              {productError && <p id="product-error" className="message message-error" role="alert">{productError}</p>}

              <div className="lookup">
                <dl className="lookup-fields">
                  <div>
                    <dt>名称</dt>
                    <dd data-testid="found-name">{found?.product_name ?? ""}</dd>
                  </div>
                  <div>
                    <dt>単価（税抜）</dt>
                    <dd data-testid="found-price">{found ? yen(found.unit_price) : ""}</dd>
                  </div>
                </dl>
                <button type="button" className="btn btn-primary" disabled={!found} onClick={addFound}>
                  購入リストに追加
                </button>
              </div>
              {cartNotice && <p className="message message-warn" role="status">{cartNotice}</p>}
            </fieldset>
          </section>
        </div>

        {/* 購入リスト（レシート） */}
        <aside className="receipt" aria-labelledby="h-cart">
          <div className="receipt-paper">
            <div className="receipt-head">
              <h2 id="h-cart" className="receipt-title">購入リスト</h2>
              <span className="receipt-customer">
                {customer.kind === "member" ? `${customer.name} 様` : customer.kind === "guest" ? "非会員" : ""}
              </span>
            </div>

            {cart.length === 0 ? (
              <p className="receipt-empty">商品を読み込んで追加すると、ここに並びます。</p>
            ) : (
              <table className="receipt-table">
                <thead>
                  <tr>
                    <th scope="col">商品</th>
                    <th scope="col" className="num">数量</th>
                    <th scope="col" className="num">単価</th>
                    <th scope="col" className="num">小計</th>
                  </tr>
                </thead>
                <tbody>
                  {cart.map((item) => (
                    <tr key={item.productCode} data-testid="cart-row">
                      <td>
                        <span className="item-name">{item.productName}</span>
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => setCart(removeFromCart(cart, item.productCode))}
                          aria-label={`${item.productName}を削除`}
                        >
                          削除
                        </button>
                      </td>
                      <td className="num">
                        <span className="qty">
                          <button type="button" className="qty-btn" aria-label={`${item.productName}を1つ減らす`}
                            disabled={item.quantity <= 1}
                            onClick={() => setCart(changeQuantity(cart, item.productCode, -1))}>−</button>
                          <span data-testid="qty">{item.quantity}</span>
                          <button type="button" className="qty-btn" aria-label={`${item.productName}を1つ増やす`}
                            disabled={item.quantity >= 99}
                            onClick={() => setCart(changeQuantity(cart, item.productCode, 1))}>＋</button>
                        </span>
                      </td>
                      <td className="num">{yen(item.unitPrice)}</td>
                      <td className="num">{yen(lineSubtotal(item))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="receipt-foot">
              <div className="receipt-sum">
                <span>{cartCount(cart)}点　税抜小計</span>
                <span className="receipt-sum-value" data-testid="cart-subtotal">{yen(cartSubtotal(cart))}</span>
              </div>
              <p className="receipt-note">消費税と税込合計は、確定時にサーバーで計算します。</p>
              {submitError && <p className="message message-error" role="alert">{submitError}</p>}
              {!submitError && confirmHint && <p className="message">{confirmHint}</p>}
              <button
                type="button"
                className="btn btn-confirm btn-block"
                disabled={!canConfirm}
                onClick={confirmPurchase}
              >
                {submitting ? "確定しています…" : "会計を確定"}
              </button>
            </div>
          </div>
        </aside>
      </main>

      {result && <TotalDialog result={result} onClose={nextCustomer} />}
    </div>
  );
}
