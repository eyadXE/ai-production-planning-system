import "./globals.css";

export const metadata = {
  title: "Ousus Production Platform",
  description:
    "Ousus delivers reliable steel fabrication — mezzanines, staircases, railings and more — planned with discipline.",
};

export const viewport = {
  colorScheme: "dark",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
