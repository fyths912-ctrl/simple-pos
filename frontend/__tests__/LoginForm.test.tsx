import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LoginForm } from "@/components/LoginForm";
import { ApiError, type Api } from "@/lib/api";
import { MSG } from "@/lib/messages";

function setup(login: Api["login"], notice: string | null = null) {
  const onSuccess = jest.fn();
  const api = { login } as unknown as Api;
  render(<LoginForm api={api} notice={notice} onSuccess={onSuccess} />);
  return { onSuccess, user: userEvent.setup() };
}

async function fill(user: ReturnType<typeof userEvent.setup>, id: string, pw: string) {
  await user.type(screen.getByLabelText("担当者ID"), id);
  await user.type(screen.getByLabelText("パスワード"), pw);
  await user.click(screen.getByRole("button", { name: "ログイン" }));
}

describe("S-01 ログイン画面", () => {
  test("T-008 成功すると POS 画面へ進む", async () => {
    const login = jest.fn().mockResolvedValue({ cashier: { cashier_id: "C001", cashier_name: "山田" } });
    const { user, onSuccess } = setup(login);
    await fill(user, "C001", "correct-pass");
    expect(login).toHaveBeenCalledWith("C001", "correct-pass");
    expect(onSuccess).toHaveBeenCalledWith({ cashier_id: "C001", cashier_name: "山田" });
  });

  test("T-006 失敗時は ID 有無が分からない文言だけ出す", async () => {
    const login = jest.fn().mockRejectedValue(new ApiError(401, "AUTH_FAILED", "x"));
    const { user, onSuccess } = setup(login);
    await fill(user, "C001", "wrong-pass");
    expect(await screen.findByRole("alert")).toHaveTextContent(MSG.authFailed);
    expect(screen.getByLabelText("パスワード")).toHaveValue("");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  test("T-004 7文字のパスワードは送信しない", async () => {
    const login = jest.fn();
    const { user } = setup(login);
    await fill(user, "C001", "1234567");
    expect(screen.getByRole("alert")).toHaveTextContent(MSG.passwordLength);
    expect(login).not.toHaveBeenCalled();
  });

  test("T-067 セッション切れの案内を表示する", () => {
    setup(jest.fn(), MSG.sessionExpired);
    expect(screen.getByRole("status")).toHaveTextContent(MSG.sessionExpired);
  });
});
