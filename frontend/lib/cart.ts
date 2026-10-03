import type { CartItem, Product } from "./types";

export const MAX_QUANTITY = 99;

/**
 * 購入リストへ追加（F-002）。同じ商品は行を増やさず数量+1。
 * 99個に達している場合は増やさず capped=true を返す（暫定仕様：頭打ち＋メッセージ）。
 */
export function addToCart(items: CartItem[], product: Product): { items: CartItem[]; capped: boolean } {
  const index = items.findIndex((i) => i.productCode === product.product_code);
  if (index === -1) {
    return {
      items: [
        ...items,
        { productCode: product.product_code, productName: product.product_name, unitPrice: product.unit_price, quantity: 1 },
      ],
      capped: false,
    };
  }
  if (items[index].quantity >= MAX_QUANTITY) return { items, capped: true };
  const next = items.slice();
  next[index] = { ...next[index], quantity: next[index].quantity + 1 };
  return { items: next, capped: false };
}

/** 数量を ±1。1未満にはしない（削除は removeFromCart）。 */
export function changeQuantity(items: CartItem[], productCode: string, delta: 1 | -1): CartItem[] {
  return items.map((i) =>
    i.productCode === productCode
      ? { ...i, quantity: Math.min(MAX_QUANTITY, Math.max(1, i.quantity + delta)) }
      : i,
  );
}

export function removeFromCart(items: CartItem[], productCode: string): CartItem[] {
  return items.filter((i) => i.productCode !== productCode);
}

export function lineSubtotal(item: CartItem): number {
  return item.unitPrice * item.quantity;
}

export function cartSubtotal(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + lineSubtotal(i), 0);
}

export function cartCount(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + i.quantity, 0);
}
