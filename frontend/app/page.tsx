"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PosScreen } from "@/components/PosScreen";
import { api } from "@/lib/api";
import type { Cashier } from "@/lib/types";

/** S-02 POSメイン画面。未ログインならログイン画面へ戻す（T-008／NF-007）。 */
export default function PosPage() {
  const router = useRouter();
  const [cashier, setCashier] = useState<Cashier | null>(null);

  useEffect(() => {
    api.me().then(setCashier).catch(() => router.replace("/login"));
  }, [router]);

  if (!cashier) return <p className="loading">読み込んでいます…</p>;

  return (
    <PosScreen
      cashier={cashier}
      onSessionExpired={() => router.replace("/login?reason=expired")}
      onLogout={async () => {
        await api.logout().catch(() => undefined);
        router.replace("/login");
      }}
    />
  );
}
