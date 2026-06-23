import Link from "next/link";

/**
 * Root page for the M6-B frontend build scaffold.
 *
 * Minimal entry point that links to the static offseason viewer at
 * /offseason. No API calls, no data fetching, no styling frameworks.
 *
 * Milestone: M6-B.
 */

export default function HomePage() {
  return (
    <main
      style={{
        padding: 24,
        fontFamily: "system-ui, sans-serif",
        maxWidth: 800,
        margin: "0 auto",
      }}
    >
      <h1 style={{ margin: 0 }}>FrontOffice-Offseason-Agent</h1>
      <p style={{ color: "#666", marginTop: 8 }}>
        Deterministic NBA offseason front-office decision workflow demo.
        Sample data only. Preview only. Requires human approval.
      </p>
      <p style={{ marginTop: 16 }}>
        <Link
          href="/offseason"
          style={{
            color: "#2563eb",
            textDecoration: "underline",
            fontWeight: 600,
          }}
        >
          Open offseason proposal viewer &rarr;
        </Link>
      </p>
      <p style={{ color: "#888", fontSize: 12, marginTop: 24 }}>
        No LLM · No MCP · No external NBA API · No data mutation
      </p>
    </main>
  );
}
