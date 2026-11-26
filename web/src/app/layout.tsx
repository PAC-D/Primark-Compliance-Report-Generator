import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { TopBar } from "@/components/TopBar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { THEME_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: { default: "TPS Compliance", template: "%s – TPS Compliance" },
  description: "Primark TPS supplier compliance and KPI dashboard, run by PAC-D",
};

// Inter's Latin variable file, as in Carton Connect: in the repo, so a build never needs Google.
const inter = localFont({ src: "./fonts/inter-latin.woff2", weight: "100 900", display: "swap", variable: "--font-inter" });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: THEME_SCRIPT sets data-theme before React hydrates
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <TooltipProvider>
          <a href="#content" className="skip">Skip to content</a>
          <TopBar />
          <main id="content" tabIndex={-1}>{children}</main>
          <footer className="site-footer">© {new Date().getFullYear()} PAC-D</footer>
          <Toaster position="bottom-center" />
        </TooltipProvider>
      </body>
    </html>
  );
}
