"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createBrowserClient } from "@/lib/supabase/client";

type LogoutButtonProps = {
  className?: string;
  children?: React.ReactNode;
};

export function LogoutButton({
  className = "",
  children = "Sign out",
}: LogoutButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    const supabase = createBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      disabled={loading}
      className={`text-sm text-foreground-secondary transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      {loading ? "Signing out…" : children}
    </button>
  );
}
