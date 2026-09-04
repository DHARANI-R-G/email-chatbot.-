import type { ReactNode } from "react";
import "./global.css";

export const metadata = {
  title: "Email Intelligence",
  description: "Email Intelligence Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}