import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "bucks.ai — Turn a startup idea into an execution-ready MVP",
  description:
    "bucks.ai researches, plans, deploys, validates, and coordinates agents to turn a founder's idea into a launched MVP workspace.",
  openGraph: {
    title: "bucks.ai — Turn a startup idea into an execution-ready MVP",
    description:
      "bucks.ai researches, plans, deploys, validates, and coordinates agents to turn a founder's idea into a launched MVP workspace.",
    type: "website",
  },
};

// Promote the saved theme before first paint. Default to dark for the
// dark-first Mission Control design.
const themeInit = `(function(){try{var s=localStorage.getItem('bucks-theme');var t=s==='light'||s==='dark'?s:'dark';document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={cn(
        spaceGrotesk.variable,
        dmSans.variable,
        jetbrainsMono.variable,
        "h-full font-sans antialiased",
      )}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
