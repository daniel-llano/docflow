import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocFlow",
  description: "Upload documents and get summaries, keywords, amounts, dates, and masked personal data back.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
