import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Noto_Sans_SC } from "next/font/google";
import "./globals.css";
import ClientProvider from "@/i18n/ClientProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Chinese font for CJK characters
const notoSansSc = Noto_Sans_SC({
  variable: "--font-noto-sans-sc",
  subsets: ["latin"], // placeholder to avoid fetch; we use it for CJK fallback
  weight: ["100", "300", "400", "500", "700", "900"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "VideoAgent — AI 视频剪辑助手",
  description: "视频 → 字幕 → 分析 → 智能剪辑",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh"
      className={`${geistSans.variable} ${geistMono.variable} ${notoSansSc.variable} h-full antialiased`}
    >
      <body className="h-full flex flex-col">
        <ClientProvider locale="zh">{children}</ClientProvider>
      </body>
    </html>
  );
}
