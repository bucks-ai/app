import type { Metadata } from "next";
import {
  DM_Sans,
  EB_Garamond,
  JetBrains_Mono,
  Space_Grotesk,
} from "next/font/google";
import "./globals.css";
import PostHogProvider from "@/components/PostHogProvider";
import { cn } from "@/lib/utils";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

// Editorial display face. Carries the headline moments — hero, section
// openers, workspace titles — so the product reads considered rather than
// instrument-panel technical. Space Grotesk stays for compact UI headings.
//
// weight: only 500 (display headings) and 400 (.display-accent italic) are
// used; 600 was being shipped for nothing.
//
// preload: false because the italic is only rendered on /, /login, and
// /signup, but Next hoists preload links from the root layout onto every
// route — so /dashboard, /tools, and /intake were each eagerly fetching a
// ~47KB italic file they never use. Fonts are not in the render-blocking
// path here and `display: swap` plus Next's fallback metrics keep CLS at 0,
// so letting CSS discovery pull them is the better trade.
const ebGaramond = EB_Garamond({
  variable: "--font-eb-garamond",
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  display: "swap",
  preload: false,
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
        ebGaramond.variable,
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
      <body className="min-h-full flex flex-col">
        {/* Every route puts six nav items ahead of its content. The <main>
            landmark covers screen readers, but keyboard-only users without
            one had no way past the header. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2.5 focus:text-sm focus:font-semibold focus:text-accent-contrast focus:shadow-[var(--shadow-cta)]"
        >
          Skip to content
        </a>
        <PostHogProvider>{children}</PostHogProvider>
      </body>
    </html>
  );
}
