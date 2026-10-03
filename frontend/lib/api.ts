import { MSG } from "./messages";
import type { Cashier, Member, Product, SalesMode, TransactionResult } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-POS-Request": "1", ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", MSG.network);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(res.status, err?.code ?? "HTTP_ERROR", err?.message ?? MSG.network);
  }
  return data as T;
}

export interface TransactionRequest {
  member_id: string | null;
  sales_mode: SalesMode;
  idempotency_key: string;
  items: { product_code: string; quantity: number }[];
}

export const api = {
  login: (cashier_id: string, password: string) =>
    request<{ cashier: Cashier }>("/api/auth/login", { method: "POST", body: JSON.stringify({ cashier_id, password }) }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  me: () => request<Cashier>("/api/auth/me"),
  getMember: (memberId: string) => request<Member>(`/api/members/${encodeURIComponent(memberId)}`),
  getProduct: (code: string) => request<Product>(`/api/products/${encodeURIComponent(code)}`),
  createTransaction: (body: TransactionRequest) =>
    request<TransactionResult>("/api/transactions", { method: "POST", body: JSON.stringify(body) }),
};

export type Api = typeof api;
