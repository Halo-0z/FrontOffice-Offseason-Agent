import type { Metadata } from "next";

/**
 * Root layout for the M6-B frontend build scaffold.
 *
 * Minimal html/body shell + metadata. No styling frameworks, no
 * providers, no API calls. The static viewer lives at /offseason.
 *
 * Milestone: M6-B.
 */

export const metadata: Metadata = {
  title: "FrontOffice-Offseason-Agent",
  description:
    "Deterministic NBA offseason front-office decision workflow demo (sample data, preview only).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          background: "#ffffff",
          color: "#111111",
        }}
      >
        {children}
      </body>
    </html>
  );
}
