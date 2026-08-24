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
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('ousus_theme')||'dark';document.documentElement.classList.remove('dark','light');document.documentElement.classList.add(t);}catch(e){}`,
          }}
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
