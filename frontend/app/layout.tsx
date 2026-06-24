import type { Metadata } from "next";
import "./globals.css";

/**
 * Root layout for the frontend.
 *
 * Imports globals.css (M6-C editorial sport-page aesthetic with
 * CJK-friendly system font stack). No styling frameworks, no
 * providers, no API calls. The static viewer lives at /offseason.
 *
 * Milestone: M6-C (Chinese-first / bilingual patch).
 */

export const metadata: Metadata = {
  title: "FrontOffice-Offseason-Agent",
  description:
    "NBA 休赛期前台决策演示：使用样例薪资、阵容、自由球员、规则检查和证据数据，生成可检查的签约 / 暂不行动预览。仅供预览，需要人工确认，不执行交易。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  );
}
