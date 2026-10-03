import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PosScreen } from "@/components/PosScreen";
import { ApiError, type Api } from "@/lib/api";
import { MSG } from "@/lib/messages";
import type { Product, TransactionResult } from "@/lib/types";

const CURRY: Product = { product_code: "4900000000011", product_name: "カレーライス", unit_price: 850 };
const SALAD: Product = { product_code: "4900000000066", product_name: "ミックスサラダ", unit_price: 450 };
const RESULT: TransactionResult = {
  transaction_id: "T20260915000001", subtotal_excl_tax: 2150, tax_amount: 215, total_incl_tax: 2365,
  transaction_at: "2026-09-15T12:00:00+09:00",
};

function mockApi(overrides: Partial<Api> = {}): jest.Mocked<Api> {
  const products: Record<string, Product> = { [CURRY.product_code]: CURRY, [SALAD.product_code]: SALAD };
  return {
    login: jest.fn(),
    logout: jest.fn(),
    me: jest.fn(),
    getMember: jest.fn(async (id: string) => {
      if (id === "M000123") return { member_id: id, display_name: "山田 太郎" };
      throw new ApiError(404, "MEMBER_NOT_FOUND", MSG.memberNotFound);
    }),
    getProduct: jest.fn(async (code: string) => {
      if (products[code]) return products[code];
      throw new ApiError(404, "PRODUCT_NOT_FOUND", MSG.productNotFound);
    }),
    createTransaction: jest.fn(async () => RESULT),
    ...overrides,
  } as jest.Mocked<Api>;
}

function setup(api = mockApi()) {
  const onSessionExpired = jest.fn();
  const user = userEvent.setup();
  render(
    <PosScreen cashier={{ cashier_id: "C001", cashier_name: "山田" }} api={api}
      onSessionExpired={onSessionExpired} onLogout={jest.fn()} />,
  );
  return { api, user, onSessionExpired };
}

const confirmButton = () => screen.getByRole("button", { name: /会計を確定|確定しています/ });

async function startGuest(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "非会員として開始" }));
}

async function addProduct(user: ReturnType<typeof userEvent.setup>, code: string) {
  const input = screen.getByLabelText("商品コード");
  await user.clear(input);
  await user.type(input, code);
  await user.click(screen.getByRole("button", { name: "読み込み" }));
  await user.click(await screen.findByRole("button", { name: "購入リストに追加" }));
}

async function readyToConfirm(user: ReturnType<typeof userEvent.setup>) {
  await startGuest(user);
  await addProduct(user, CURRY.product_code);
  await user.click(screen.getByRole("radio", { name: /店内/ }));
}

describe("S-02 POSメイン画面", () => {
  test("担当者情報を表示する", () => {
    setup();
    expect(screen.getByTestId("cashier")).toHaveTextContent("担当 山田（C001）");
  });

  test("T-011 会員IDを読み込むと表示名だけが出る", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("会員ID"), "m000123");
    await user.click(screen.getByRole("button", { name: "会員を読み込む" }));
    expect(await screen.findByTestId("member-name")).toHaveTextContent("山田 太郎 様");
  });

  test("T-012 未登録の会員IDはメッセージを出し、入力状態のまま", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("会員ID"), "M999999");
    await user.click(screen.getByRole("button", { name: "会員を読み込む" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(MSG.memberNotFound);
    expect(screen.getByLabelText("会員ID")).toHaveValue("M999999");
    expect(screen.getByRole("button", { name: "非会員として開始" })).toBeInTheDocument();
  });

  test("T-014 非会員として開始すると member_id=null で確定される", async () => {
    const { user, api } = setup();
    await readyToConfirm(user);
    expect(screen.queryByTestId("member-name")).not.toBeInTheDocument();
    await user.click(confirmButton());
    expect(api.createTransaction).toHaveBeenCalledWith(expect.objectContaining({ member_id: null }));
  });

  test("商品はお客様を選ぶまで操作できない", () => {
    setup();
    expect(screen.getByLabelText("商品コード")).toBeDisabled();
  });

  test("T-016 取引区分が未選択だと確定ボタンは押せない", async () => {
    const { user } = setup();
    await startGuest(user);
    await addProduct(user, CURRY.product_code);
    expect(confirmButton()).toBeDisabled();
    expect(screen.getByText(MSG.salesModeRequired)).toBeInTheDocument();
  });

  test("T-015/T-017 取引区分は最後に選んだものが送られる", async () => {
    const { user, api } = setup();
    await readyToConfirm(user);
    await user.click(screen.getByRole("radio", { name: /持ち帰り/ }));
    await user.click(confirmButton());
    expect(api.createTransaction).toHaveBeenCalledWith(expect.objectContaining({ sales_mode: "TAKEOUT" }));
  });

  test("T-019 商品を読み込むと名称と単価が出る（前後の空白は除去）", async () => {
    const { user, api } = setup();
    await startGuest(user);
    await user.type(screen.getByLabelText("商品コード"), ` ${CURRY.product_code} `);
    await user.click(screen.getByRole("button", { name: "読み込み" }));
    expect(await screen.findByTestId("found-name")).toHaveTextContent("カレーライス");
    expect(screen.getByTestId("found-price")).toHaveTextContent("850円");
    expect(api.getProduct).toHaveBeenCalledWith(CURRY.product_code);
  });

  test("T-020 未登録の商品はメッセージを出し、購入リストは残る", async () => {
    const { user } = setup();
    await startGuest(user);
    await addProduct(user, CURRY.product_code);
    await user.type(screen.getByLabelText("商品コード"), "4999999999999");
    await user.click(screen.getByRole("button", { name: "読み込み" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(MSG.productNotFound);
    expect(screen.getByTestId("found-name")).toHaveTextContent("");
    expect(screen.getAllByTestId("cart-row")).toHaveLength(1);
  });

  test("商品コードの形式が違うときは API を呼ばない", async () => {
    const { user, api } = setup();
    await startGuest(user);
    await user.type(screen.getByLabelText("商品コード"), "123");
    await user.click(screen.getByRole("button", { name: "読み込み" }));
    expect(screen.getByRole("alert")).toHaveTextContent(MSG.productCodeFormat);
    expect(api.getProduct).not.toHaveBeenCalled();
  });

  test("T-024 読み込み前は追加できない", async () => {
    const { user } = setup();
    await startGuest(user);
    expect(screen.getByRole("button", { name: "購入リストに追加" })).toBeDisabled();
  });

  test("T-022/T-023/T-026 追加すると行が増え、同じ商品は数量が増え、入力欄は空になる", async () => {
    const { user } = setup();
    await startGuest(user);
    await addProduct(user, CURRY.product_code);
    expect(screen.getByLabelText("商品コード")).toHaveValue("");
    expect(screen.getByTestId("found-name")).toHaveTextContent("");
    expect(screen.getByTestId("found-price")).toHaveTextContent("");
    await addProduct(user, CURRY.product_code);
    await addProduct(user, SALAD.product_code);
    const rows = screen.getAllByTestId("cart-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByTestId("qty")).toHaveTextContent("2");
    expect(screen.getByTestId("cart-subtotal")).toHaveTextContent("2,150円");
  });

  test("T-031 購入リストが空だと確定ボタンは押せない", async () => {
    const { user } = setup();
    await startGuest(user);
    await user.click(screen.getByRole("radio", { name: /店内/ }));
    expect(confirmButton()).toBeDisabled();
    expect(screen.getByText(MSG.emptyCart)).toBeInTheDocument();
  });

  test("T-036 単価や合計は送らず、商品コードと数量だけ送る", async () => {
    const { user, api } = setup();
    await readyToConfirm(user);
    await user.click(confirmButton());
    const sent = api.createTransaction.mock.calls[0][0];
    expect(sent.items).toEqual([{ product_code: CURRY.product_code, quantity: 1 }]);
    expect(sent.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  });

  test("T-038/T-044 確定ボタンの連打でも送信は1回", async () => {
    let resolve!: (r: TransactionResult) => void;
    const api = mockApi({ createTransaction: jest.fn(() => new Promise<TransactionResult>((r) => (resolve = r))) });
    const { user } = setup(api);
    await readyToConfirm(user);
    const button = confirmButton();
    await act(async () => {
      button.click();
      button.click();
      button.click();
    });
    expect(api.createTransaction).toHaveBeenCalledTimes(1);
    expect(confirmButton()).toBeDisabled();
    await act(async () => resolve(RESULT));
  });

  test("T-037 保存失敗ではリストを残し、再試行は同じ冪等性キーで送る", async () => {
    const api = mockApi({
      createTransaction: jest.fn()
        .mockRejectedValueOnce(new ApiError(500, "TRANSACTION_SAVE_FAILED", "x"))
        .mockResolvedValueOnce(RESULT),
    });
    const { user } = setup(api);
    await readyToConfirm(user);
    await user.click(confirmButton());
    expect(await screen.findByRole("alert")).toHaveTextContent(MSG.saveFailed);
    expect(screen.getAllByTestId("cart-row")).toHaveLength(1);
    await user.click(confirmButton());
    const [first, second] = api.createTransaction.mock.calls.map((c) => c[0].idempotency_key);
    expect(second).toBe(first);
  });

  test("会計内容を変えたら冪等性キーも変わる", async () => {
    const api = mockApi({
      createTransaction: jest.fn()
        .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", MSG.network))
        .mockResolvedValueOnce(RESULT),
    });
    const { user } = setup(api);
    await readyToConfirm(user);
    await user.click(confirmButton());
    await addProduct(user, SALAD.product_code);
    await user.click(confirmButton());
    const [first, second] = api.createTransaction.mock.calls.map((c) => c[0].idempotency_key);
    expect(second).not.toBe(first);
  });

  test("T-046 確定後に金額を表示し、閉じると次のお客様の状態に戻る", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("会員ID"), "M000123");
    await user.click(screen.getByRole("button", { name: "会員を読み込む" }));
    await screen.findByTestId("member-name");
    await addProduct(user, CURRY.product_code);
    await user.click(screen.getByRole("radio", { name: /店内/ }));
    await user.click(confirmButton());

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/T20260915000001/)).toBeInTheDocument();
    expect(within(dialog).getByTestId("subtotal")).toHaveTextContent("2,150円");
    expect(within(dialog).getByTestId("tax")).toHaveTextContent("215円");
    expect(within(dialog).getByTestId("total")).toHaveTextContent("2,365円");

    await user.click(within(dialog).getByRole("button", { name: "閉じて次のお客様へ" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("会員ID")).toHaveValue("");
    expect(screen.queryAllByTestId("cart-row")).toHaveLength(0);
    expect(screen.getByRole("radio", { name: /店内/ })).not.toBeChecked();
  });

  test("T-053 会計途中のセッション切れはログイン画面へ", async () => {
    const api = mockApi({ getProduct: jest.fn().mockRejectedValue(new ApiError(401, "UNAUTHORIZED", MSG.sessionExpired)) });
    const { user, onSessionExpired } = setup(api);
    await startGuest(user);
    await user.type(screen.getByLabelText("商品コード"), CURRY.product_code);
    await user.click(screen.getByRole("button", { name: "読み込み" }));
    expect(onSessionExpired).toHaveBeenCalled();
  });

  test.each([
    ["EMPTY_CART", 400, MSG.emptyCart],
    ["MEMBER_NOT_FOUND", 404, MSG.memberNotFound],
    ["PRODUCT_CHANGED_OR_NOT_FOUND", 409, MSG.productChanged],
    ["TRANSACTION_SAVE_FAILED", 500, MSG.saveFailed],
  ])("T-067 確定時のエラー %s の文言", async (code, status, message) => {
    const api = mockApi({ createTransaction: jest.fn().mockRejectedValue(new ApiError(status, code, "server")) });
    const { user } = setup(api);
    await readyToConfirm(user);
    await user.click(confirmButton());
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  test("T-059 商品名に含まれるタグは文字として表示される", async () => {
    const evil: Product = { product_code: "4900000000999", product_name: "<img src=x onerror=alert(1)>", unit_price: 1 };
    const api = mockApi({ getProduct: jest.fn().mockResolvedValue(evil) });
    const { user } = setup(api);
    await startGuest(user);
    await addProduct(user, evil.product_code);
    expect(screen.getByText(evil.product_name)).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });
});
