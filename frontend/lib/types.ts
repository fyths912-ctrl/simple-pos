export type SalesMode = "DINE_IN" | "TAKEOUT";

export interface Cashier {
  cashier_id: string;
  cashier_name: string;
}

export interface Member {
  member_id: string;
  display_name: string;
}

export interface Product {
  product_code: string;
  product_name: string;
  unit_price: number;
}

export interface CartItem {
  productCode: string;
  productName: string;
  unitPrice: number; // 表示用。請求額は購入確定 API の再計算結果を使う
  quantity: number;
}

export interface TransactionResult {
  transaction_id: string;
  subtotal_excl_tax: number;
  tax_amount: number;
  total_incl_tax: number;
  transaction_at: string;
}
