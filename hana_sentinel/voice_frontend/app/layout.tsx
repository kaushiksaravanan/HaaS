import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HANA Sentinel Voice",
  description: "Talk to HANA Ops Agent — SAP HANA AI Operations Assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
