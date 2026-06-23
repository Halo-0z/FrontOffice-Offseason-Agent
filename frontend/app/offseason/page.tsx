/**
 * Offseason simulator page.
 *
 * M0 placeholder. Renders a minimal header and the five panel
 * components so the layout is visible. No data fetching, no API calls.
 *
 * Milestone: M5.
 */

import CapSheetPanel from "../../components/CapSheetPanel";
import TransactionPlanCard from "../../components/TransactionPlanCard";
import DepthChartPreview from "../../components/DepthChartPreview";
import EvidencePanel from "../../components/EvidencePanel";
import ApprovalControls from "../../components/ApprovalControls";

export default function OffseasonPage() {
  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1>FrontOffice-Offseason-Agent</h1>
      <p>NBA offseason front-office transaction simulation agent.</p>

      <section style={{ display: "grid", gap: 16, marginTop: 24 }}>
        <CapSheetPanel />
        <TransactionPlanCard />
        <DepthChartPreview />
        <EvidencePanel />
        <ApprovalControls />
      </section>

      <footer style={{ marginTop: 32, color: "#666", fontSize: 12 }}>
        M0 skeleton. No live data, no LLM, no state mutation.
      </footer>
    </main>
  );
}
