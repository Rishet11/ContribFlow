import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ContribFlow — Your First Open Source Contribution Starts Here",
  description:
    "AI-powered guide that finds the right issue, explains the codebase, and gives you a clear plan to make your first open source contribution.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
