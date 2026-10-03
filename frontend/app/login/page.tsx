"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LoginForm } from "@/components/LoginForm";
import { MSG } from "@/lib/messages";

export default function LoginPage() {
  const router = useRouter();
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "expired") setNotice(MSG.sessionExpired);
  }, []);

  return (
    <main className="login-page">
      <LoginForm notice={notice} onSuccess={() => router.replace("/")} />
    </main>
  );
}
