"use client";

export default function GlobalError({ error, reset }) {
  return (
    <html lang="en">
      <body style={{ background: "#0f1117", color: "#e6e9f0", fontFamily: "monospace" }}>
        <div style={{ display: "flex", minHeight: "100vh", flexDirection: "column",
                      alignItems: "center", justifyContent: "center", gap: 16, padding: 24,
                      textAlign: "center" }}>
          <h2 style={{ fontSize: 18 }}>Application error</h2>
          <p style={{ fontSize: 12, color: "#8b93a7", maxWidth: 480 }}>
            {String(error?.message || "Unknown error").slice(0, 200)}
          </p>
          <div style={{ display: "flex", gap: 12 }}>
            <button onClick={reset}
                    style={{ background: "#1cbac8", color: "#10222a", border: "none",
                             padding: "10px 16px", fontSize: 12, cursor: "pointer" }}>
              Try again
            </button>
            <a href="/" style={{ border: "1px solid #262b38", color: "#8b93a7",
                                 padding: "10px 16px", fontSize: 12, textDecoration: "none" }}>
              Go home
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
