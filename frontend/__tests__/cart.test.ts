import { addToCart, cartCount, cartSubtotal, changeQuantity, MAX_QUANTITY, removeFromCart } from "@/lib/cart";
import type { Product } from "@/lib/types";

const curry: Product = { product_code: "4900000000011", product_name: "カレーライス", unit_price: 850 };
const salad: Product = { product_code: "4900000000066", product_name: "ミックスサラダ", unit_price: 450 };

describe("購入リスト（F-002）", () => {
  test("T-022 新しい商品は数量1の行として追加される", () => {
    const { items } = addToCart([], curry);
    expect(items).toEqual([{ productCode: curry.product_code, productName: "カレーライス", unitPrice: 850, quantity: 1 }]);
  });

  test("T-023 同じ商品は行を増やさず数量+1", () => {
    let items = addToCart([], curry).items;
    items = addToCart(items, salad).items;
    items = addToCart(items, curry).items;
    expect(items).toHaveLength(2);
    expect(items[0].quantity).toBe(2);
  });

  test("T-025 99回追加で99、100回目は頭打ちで capped", () => {
    let items = [] as ReturnType<typeof addToCart>["items"];
    for (let i = 0; i < 99; i++) items = addToCart(items, curry).items;
    expect(items[0].quantity).toBe(MAX_QUANTITY);
    const hundredth = addToCart(items, curry);
    expect(hundredth.capped).toBe(true);
    expect(hundredth.items[0].quantity).toBe(99);
  });

  test("数量の増減は1〜99の範囲に収まる", () => {
    const items = addToCart([], curry).items;
    expect(changeQuantity(items, curry.product_code, -1)[0].quantity).toBe(1);
    expect(changeQuantity(items, curry.product_code, 1)[0].quantity).toBe(2);
  });

  test("削除・合計・点数", () => {
    let items = addToCart([], curry).items;
    items = addToCart(items, curry).items;
    items = addToCart(items, salad).items;
    expect(cartSubtotal(items)).toBe(850 * 2 + 450);
    expect(cartCount(items)).toBe(3);
    expect(removeFromCart(items, curry.product_code)).toHaveLength(1);
  });
});
