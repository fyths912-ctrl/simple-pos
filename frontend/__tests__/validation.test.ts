import {
  isValidMemberId, isValidPasswordLength, isValidProductCode, normalizeMemberId, normalizeProductCode,
} from "@/lib/validation";

describe("入力検証", () => {
  test.each([
    ["4900000000011", true],
    ["490000000001", false],   // 12桁
    ["49000000000111", false], // 14桁
    ["49000000000A1", false],  // 英字混在
  ])("T-018 商品コード %s → %s", (code, ok) => {
    expect(isValidProductCode(code)).toBe(ok);
  });

  test("T-019 前後空白を除去、全角数字は半角にそろえる", () => {
    expect(normalizeProductCode("  4900000000011 ")).toBe("4900000000011");
    expect(normalizeProductCode("４９０００００００００１１")).toBe("4900000000011");
  });

  test.each([["M000123", true], ["M12345", false], ["M1234567", false], ["X000123", false]])(
    "T-010 会員ID %s → %s", (id, ok) => expect(isValidMemberId(id)).toBe(ok),
  );

  test("会員IDは小文字・全角でも正規化される", () => {
    expect(normalizeMemberId(" ｍ０００１２３ ")).toBe("M000123");
  });

  test.each([[7, false], [8, true], [64, true], [65, false]])("T-004 パスワード %i 文字 → %s", (n, ok) => {
    expect(isValidPasswordLength("x".repeat(n))).toBe(ok);
  });
});
