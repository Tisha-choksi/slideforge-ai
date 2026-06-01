import type { Metadata } from "next";
import { Syne, DM_Sans } from "next/font/google";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  weight: ["400", "600", "700", "800"],
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm",
  weight: ["300", "400", "500"],
});

export const metadata: Metadata = {
  title: "SlideForge AI — From idea to deck in seconds",
  description:
    "AI-powered presentation generator. Paste text, upload a doc, or drop a URL — get a polished .pptx deck in under 30 seconds. Powered by Groq AI. 100% free.",
  keywords: "AI presentation generator, PowerPoint AI, slide deck generator, free AI slides",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${syne.variable} ${dmSans.variable}`}>
      <body className="bg-[#080B14] text-white antialiased">{children}</body>
    </html>
  );
}
