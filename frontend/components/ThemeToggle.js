"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle({ className = "" }) {
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const saved = localStorage.getItem("ousus_theme") || "dark";
    setTheme(saved);
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(saved);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("ousus_theme", next);
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(next);
  }

  return (
    <button aria-label="Toggle light/dark mode" onClick={toggle}
            className={`grid size-8 place-items-center border border-border text-muted-foreground hover:text-foreground ${className}`}>
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}
