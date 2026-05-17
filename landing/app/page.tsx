"use client";

import { Hero } from "@/components/ui/animated-hero";
import {
  FeaturesSection,
  HowItWorksSection,
  SampleDigestSection,
  FAQSection,
  CTASection,
} from "@/components/sections";
import { Send, Zap } from "lucide-react";
import { LightPullThemeSwitcher } from "@/components/ui/light-pull-theme-switcher";

function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-gray-950/80 backdrop-blur-md border-b border-gray-100 dark:border-gray-800">
      <div className="container mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold text-gray-900 dark:text-white">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          AI Tech Digest
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-gray-500 dark:text-gray-400 font-medium">
          <a href="#features" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">How it works</a>
          <a href="#sample" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">Sample</a>
          <a href="#faq" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">FAQ</a>
        </div>
        <a
          href="https://t.me/aitechdigest_bot"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden sm:inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-full transition-all hover:scale-105"
        >
          <Send className="w-4 h-4" />
          Subscribe Free
        </a>
      </div>
    </nav>
  );
}

export default function Home() {
  return (
    <main className="bg-white dark:bg-gray-950">
      <div className="fixed top-0 right-4 sm:right-12 z-60">
        <LightPullThemeSwitcher />
      </div>
      <Navbar />
      <div className="pt-16">
        <Hero />
        <FeaturesSection />
        <HowItWorksSection />
        <SampleDigestSection />
        <FAQSection />
        <CTASection />
        <footer className="bg-gray-900 text-gray-400 text-sm text-center py-8">
          <p>© 2026 AI Tech Digest · Built with ❤️ by Ayush Aryan</p>
          <p className="mt-1 text-gray-600">
            Free, open, and delivered daily via Telegram
          </p>
        </footer>
      </div>
    </main>
  );
}
