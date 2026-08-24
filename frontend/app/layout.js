import "./globals.css";

export const metadata = {
  title: "Ousus Production Platform",
  description: "Steel fabrication planning & tracking",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
