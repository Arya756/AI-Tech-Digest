import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";

const poppins = Poppins({ 
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "AI Tech Digest — Your daily 3-minute AI briefing on Telegram",
  description:
    "Get the top 5 AI stories every morning — curated by AI, read aloud by Ava, delivered on Telegram. Free forever.",
  keywords: "AI news, daily digest, Telegram bot, AI briefing, artificial intelligence, tech news",
  openGraph: {
    title: "AI Tech Digest",
    description: "Your daily 3-minute AI briefing. Read less, know more.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={`${poppins.className} antialiased`}>{children}</body>
    </html>
  );
}
