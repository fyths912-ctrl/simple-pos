/** 入力の正規化と検証（サーバー側でも同じ検証を行う：設計8.4）。 */

/** 全角数字・全角英字を半角に（日本語入力のままでも読めるように） */
export function toHalfWidth(value: string): string {
  return value.replace(/[０-９Ａ-Ｚａ-ｚ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));
}

export function normalizeProductCode(value: string): string {
  return toHalfWidth(value).trim();
}

export function isValidProductCode(code: string): boolean {
  return /^[0-9]{13}$/.test(code);
}

export function normalizeMemberId(value: string): string {
  return toHalfWidth(value).trim().toUpperCase();
}

export function isValidMemberId(id: string): boolean {
  return /^M[0-9]{6}$/.test(id);
}

export function isValidPasswordLength(pw: string): boolean {
  return pw.length >= 8 && pw.length <= 64;
}
