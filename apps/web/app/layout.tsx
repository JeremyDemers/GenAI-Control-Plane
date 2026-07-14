import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Access Control Center",
  description: "Governed temporary access control plane for enterprise GenAI services"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

