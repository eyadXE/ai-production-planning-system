"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Error({ error, reset }) {
  useEffect(() => {
    console.error("Page error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="font-mono text-lg font-bold text-foreground">
        Something went wrong on this page
      </h2>
      <p className="max-w-md font-mono text-xs leading-6 text-muted-foreground">
        {String(error?.message || "Unknown error").slice(0, 200)}
      </p>
      <div className="flex gap-3">
        <button onClick={reset}
                className="bg-primary px-4 py-2.5 font-mono text-xs font-bold text-primary-foreground hover:opacity-90">
          Try again
        </button>
        <Link href="/"
              className="border border-border px-4 py-2.5 font-mono text-xs text-muted-foreground hover:text-foreground">
          Go home
        </Link>
      </div>
    </div>
  );
}
