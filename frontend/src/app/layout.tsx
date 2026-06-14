import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

/** Origin of the FastAPI backend, used to warm the connection before the first
    /health probe fires. Falls back to null when the env var is unset/invalid. */
const apiOrigin = (() => {
  try {
    return new URL(
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
    ).origin;
  } catch {
    return null;
  }
})();

export const metadata: Metadata = {
  title: "Ops Diagnostic Agent — Evidence to Blueprint",
  description:
    "Upload operational evidence and generate cited automation blueprints with a multi-agent diagnostic engine.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="relative min-h-full flex flex-col">
        {apiOrigin ? (
          <>
            {/* React 19 hoists these resource hints into <head>. */}
            <link rel="preconnect" href={apiOrigin} crossOrigin="anonymous" />
            <link rel="dns-prefetch" href={apiOrigin} />
          </>
        ) : null}
        {children}
      </body>
    </html>
  );
}
