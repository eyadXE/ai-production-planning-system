"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "../lib/api";
import Nav from "../components/Nav";

export default function Home() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const user = getUser();

  useEffect(() => {
    if (!user) router.replace("/login");
    else if (user.role === "client") router.replace("/my");
    else router.replace("/board");
    setReady(true);
  }, []);

  return (
    <>
      <Nav />
      <div className="container">{ready && !user ? "Redirecting…" : ""}</div>
    </>
  );
}
