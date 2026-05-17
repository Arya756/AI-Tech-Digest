"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  Rss,
  Brain,
  Mic2,
  Send,
  Clock,
  CheckCircle2,
  Zap,
  Globe,
  ShieldCheck,
} from "lucide-react";
import { ContainerScroll } from "./ui/container-scroll-animation";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';

const features = [
  {
    icon: Rss,
    title: "9 High-Signal Sources",
    desc: "Pulls from OpenAI, Google AI, Meta AI, Microsoft, ArXiv, Hacker News, and more — filtered and weighted by credibility.",
    color: "bg-orange-50 text-orange-600 dark:bg-orange-500/10 dark:text-orange-400",
  },
  {
    icon: Brain,
    title: "AI-Powered Curation",
    desc: "Every article is scored on innovation, impact, and credibility. Only the top 5 stories make the cut each day.",
    color: "bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400",
  },
  {
    icon: CheckCircle2,
    title: "Context Included",
    desc: "Not just news — the AI explains the background. What is a supply chain attack? Why does this paper matter? Ava tells you.",
    color: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
  },
  {
    icon: Mic2,
    title: "Bilingual Voice Briefing",
    desc: "Choose English (Ava Neural) or Hindi (Madhur Neural). Your digest is read aloud in your language — perfect for your morning commute.",
    color: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
  },
  {
    icon: Send,
    title: "Delivered on Telegram",
    desc: "Formatted text message with Read More links + a voice note. All in one place, every morning.",
    color: "bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400",
  },
  {
    icon: Clock,
    title: "Your Time, Your Language",
    desc: "Pick your delivery time (7, 8, or 9 AM) and language (English or Hindi) on first launch. The bot remembers your preferences forever.",
    color: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
  },
];

function FadeInSection({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 bg-white dark:bg-gray-950">
      <div className="container mx-auto px-6">
        <FadeInSection>
          <div className="text-center mb-16">
            <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-sm uppercase tracking-wider">
              Features
            </span>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mt-3">
              Everything you need,{" "}
              <span className="text-indigo-600 dark:text-indigo-400">nothing you don't</span>
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-lg mt-4 max-w-xl mx-auto">
              Built by a developer for people who care about AI but don't have
              time to doomscroll tech Twitter.
            </p>
          </div>
        </FadeInSection>

        <div className="grid grid-cols-1 md:grid-cols-3 auto-rows-fr gap-6">
          {/* Card 1: Tall (Span 2 rows) */}
          <FadeInSection className="md:col-span-1 md:row-span-2 h-full" delay={0}>
            <div className="h-full bg-[#f3f0fe] dark:bg-purple-900/10 rounded-[2rem] p-8 relative overflow-hidden border border-purple-100/50 dark:border-purple-800/30 flex flex-col transition-transform hover:-translate-y-1">
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">9 High-Signal Sources</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed relative z-10">
                Pulls from OpenAI, Google AI, Meta AI, Microsoft, ArXiv, Hacker News, and more — filtered and weighted by credibility.
              </p>
              <div className="mt-auto pt-16 flex justify-center">
                 <Rss className="w-32 h-32 text-purple-200 dark:text-purple-800/40 relative z-0" />
              </div>
            </div>
          </FadeInSection>

          {/* Card 2: Wide (Span 2 cols) */}
          <FadeInSection className="md:col-span-2 md:row-span-1 h-full" delay={0.1}>
            <div className="h-full bg-[#fde8ee] dark:bg-pink-900/10 rounded-[2rem] p-8 relative overflow-hidden border border-pink-100/50 dark:border-pink-800/30 flex flex-col sm:flex-row items-center gap-6 transition-transform hover:-translate-y-1">
              <div className="flex-1 relative z-10">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">AI-Powered Curation</h3>
                <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed max-w-sm">
                  Every article is scored on innovation, impact, and credibility. Only the top 5 stories make the cut each day.
                </p>
              </div>
              <div className="shrink-0 relative">
                 <Brain className="w-24 h-24 text-pink-200 dark:text-pink-800/40 rotate-12" />
              </div>
            </div>
          </FadeInSection>

          {/* Card 3: Square */}
          <FadeInSection className="md:col-span-1 md:row-span-1 h-full" delay={0.2}>
            <div className="h-full bg-[#fef5d9] dark:bg-yellow-900/10 rounded-[2rem] p-8 relative overflow-hidden border border-yellow-100/50 dark:border-yellow-800/30 flex flex-col transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 relative z-10">Context Included</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed relative z-10">
                Not just news — the AI explains the background. What is a supply chain attack? Ava tells you.
              </p>
              <CheckCircle2 className="absolute -bottom-6 -right-6 w-32 h-32 text-yellow-200 dark:text-yellow-800/40 -rotate-12" />
            </div>
          </FadeInSection>

          {/* Card 4: Square */}
          <FadeInSection className="md:col-span-1 md:row-span-1 h-full" delay={0.3}>
            <div className="h-full bg-[#eef5e5] dark:bg-green-900/10 rounded-[2rem] p-8 relative overflow-hidden border border-green-100/50 dark:border-green-800/30 flex flex-col justify-end transition-transform hover:-translate-y-1">
              <Mic2 className="absolute -top-4 -right-4 w-28 h-28 text-green-200 dark:text-green-800/40 rotate-12" />
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 relative z-10 mt-12">Bilingual Voice</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed relative z-10">
                English or Hindi — both read aloud by Microsoft Neural voices. Choose your language on setup.
              </p>
            </div>
          </FadeInSection>

          {/* Card 5: Wide */}
          <FadeInSection className="md:col-span-2 md:row-span-1 h-full" delay={0.4}>
            <div className="h-full bg-[#fbe5d4] dark:bg-orange-900/10 rounded-[2rem] p-8 relative overflow-hidden border border-orange-100/50 dark:border-orange-800/30 flex flex-col sm:flex-row items-center gap-6 transition-transform hover:-translate-y-1">
              <div className="flex-1 relative z-10">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">Delivered on Telegram</h3>
                <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed max-w-sm">
                  Formatted text message with Read More links + a voice note. All in one place, every morning.
                </p>
              </div>
              <div className="shrink-0 relative">
                 <Send className="w-24 h-24 text-orange-200 dark:text-orange-800/40 -rotate-12" />
              </div>
            </div>
          </FadeInSection>

          {/* Card 6: Square */}
          <FadeInSection className="md:col-span-1 md:row-span-1 h-full" delay={0.5}>
            <div className="h-full bg-[#eff2f6] dark:bg-slate-800/20 rounded-[2rem] p-8 relative overflow-hidden border border-slate-200/50 dark:border-slate-700/50 flex flex-col transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 relative z-10">Your Time, Your Language</h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed relative z-10">
                Pick 7, 8, or 9 AM delivery and English or Hindi on first launch.
              </p>
              <Clock className="absolute -bottom-6 -right-4 w-28 h-28 text-slate-200 dark:text-slate-700/50" />
            </div>
          </FadeInSection>
        </div>
      </div>
    </section>
  );
}

const steps = [
  {
    step: "01",
    title: "We fetch the news",
    desc: "Every day, we pull fresh articles from 9 top AI sources — research labs, tech journalism, and community signals.",
    icon: Globe,
    iconBg: "bg-emerald-100 dark:bg-emerald-900/50",
    iconBorder: "border-emerald-400 dark:border-emerald-500",
    iconColor: "text-emerald-600 dark:text-emerald-400",
    rotation: "-rotate-6",
    offset: "lg:mt-0"
  },
  {
    step: "02",
    title: "AI ranks & summarizes",
    desc: "Each article is scored on innovation and impact. Only the top 5 are selected, summarized, and contextualized.",
    icon: Brain,
    iconBg: "bg-pink-100 dark:bg-pink-900/50",
    iconBorder: "border-pink-400 dark:border-pink-500",
    iconColor: "text-pink-600 dark:text-pink-400",
    rotation: "rotate-6",
    offset: "lg:mt-16"
  },
  {
    step: "03",
    title: "Voice reads it aloud",
    desc: "Microsoft Neural voices turn the digest into a natural audio briefing in your language — English (Ava) or Hindi (Madhur). Just like a podcast.",
    icon: Mic2,
    iconBg: "bg-orange-100 dark:bg-orange-900/50",
    iconBorder: "border-orange-400 dark:border-orange-500",
    iconColor: "text-orange-600 dark:text-orange-400",
    rotation: "-rotate-3",
    offset: "lg:mt-0"
  },
  {
    step: "04",
    title: "Receive on Telegram",
    desc: "Get the full text digest with links + a voice note. Tap play, listen on your commute, and go.",
    icon: Send,
    iconBg: "bg-indigo-100 dark:bg-indigo-900/50",
    iconBorder: "border-indigo-400 dark:border-indigo-500",
    iconColor: "text-indigo-600 dark:text-indigo-400",
    rotation: "rotate-12",
    offset: "lg:mt-16"
  },
];

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-24 bg-indigo-50 dark:bg-indigo-950/20 overflow-hidden relative">
      <div className="container mx-auto px-6">
        <FadeInSection>
          <div className="mb-20 max-w-2xl">
            <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-sm uppercase tracking-widest">
              How It Works
            </span>
            <h2 className="text-4xl md:text-5xl font-extrabold text-gray-900 dark:text-white mt-4 leading-tight max-w-3xl">
              Turn overwhelming AI news into your daily briefing in four simple steps
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-lg mt-4">
              Less than 3 minutes to turn catching up on AI into a breeze.
            </p>
          </div>
        </FadeInSection>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-6 relative">
          {steps.map((s, i) => (
            <div key={i} className={`relative ${s.offset}`}>
              {/* Hand-drawn zigzag arrow linking to next step (visible on lg) */}
              {i < steps.length - 1 && (
                <div className={`hidden lg:block absolute -right-12 top-1/2 z-20 text-indigo-400 dark:text-indigo-500 pointer-events-none ${
                  i % 2 === 0 ? 'translate-y-8 rotate-12' : '-translate-y-12 rotate-[-10deg]'
                }`}>
                  <svg className="w-24 h-12 drop-shadow-sm" viewBox="0 0 100 40" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
                    {/* ZigZag Shaft */}
                    <path d="M 10 25 L 40 15 L 20 35 L 85 20" />
                    {/* Asymmetric Arrowhead */}
                    <path d="M 65 10 L 85 20 L 70 30" />
                  </svg>
                </div>
              )}

              <FadeInSection delay={i * 0.15} className="h-full">
                <div className="h-full bg-white dark:bg-gray-900 rounded-3xl p-8 pt-14 shadow-sm border border-gray-100 dark:border-gray-800 relative z-10 transition-transform hover:-translate-y-2">
                  
                  {/* Playful Floating Icon */}
                  <div className={`absolute -top-6 -left-4 w-16 h-16 rounded-2xl flex items-center justify-center border-4 shadow-sm bg-white dark:bg-gray-950 ${s.iconBg} ${s.iconBorder} ${s.iconColor} ${s.rotation}`}>
                    <s.icon className="w-8 h-8 stroke-[2.5]" />
                  </div>

                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">{s.title}</h3>
                  <p className="text-gray-500 dark:text-gray-400 text-sm leading-relaxed">{s.desc}</p>
                </div>
              </FadeInSection>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SampleDigestSection() {
  const stories = [
    {
      priority: "🔥",
      label: "CRITICAL",
      title: "OpenAI launches Codex — a coding agent that writes production code",
      source: "OpenAI Blog",
      summary: "OpenAI releases Codex, an AI agent that can autonomously write, debug and ship code. Early benchmarks show it outperforms senior engineers on routine tasks.",
      context: "A coding agent is an AI that doesn't just suggest code — it actually runs it, tests it, and fixes errors in a loop without human help.",
      impact: "Developers save 10+ hours per week on boilerplate and debugging",
    },
    {
      priority: "⚡",
      label: "IMPORTANT",
      title: "Google DeepMind's new model sets SOTA on 12 benchmarks",
      source: "Google AI Blog",
      summary: "DeepMind's Gemini Ultra 2 achieves state-of-the-art results across reasoning, math, and code. The model is available via API with competitive pricing.",
      context: "SOTA (State of the Art) means the best performance ever recorded on a standardized test. DeepMind is Google's AI research lab.",
      impact: "Enterprise teams gain access to frontier reasoning at reduced cost",
    },
  ];

  return (
    <section id="sample" className="bg-white dark:bg-gray-950 flex flex-col overflow-hidden pb-80 pt-12">
      <ContainerScroll
        titleComponent={
          <>
            <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-sm uppercase tracking-widest block mb-4">
              Sample Digest
            </span>
            <h2 className="text-4xl md:text-[4rem] font-bold text-black dark:text-white mt-1 leading-none mb-8">
              This is what you get, every day
            </h2>
          </>
        }
      >
        <div className="h-full w-full rounded-2xl bg-gray-50 dark:bg-gray-900 overflow-y-auto shadow-sm flex flex-col">
          {/* Telegram-style header */}
            <div className="bg-indigo-600 dark:bg-indigo-800 px-6 py-4 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-white font-semibold text-sm">AI Tech Digest</p>
                <p className="text-indigo-200 text-xs">Bot · Delivered at your chosen time</p>
              </div>
            </div>

            {/* Message bubble */}
            <div className="p-6 space-y-6">
              <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow-sm border border-gray-100 dark:border-gray-700">
                <p className="font-bold text-gray-900 dark:text-white mb-1">🔥 AI Tech Digest — May 15, 2026</p>
                <p className="text-gray-400 dark:text-gray-500 text-sm italic">Your daily 3-minute AI briefing. Read less, know more. 🎙️</p>
                <div className="border-t border-gray-100 dark:border-gray-700 mt-4 pt-4 space-y-5">
                  {stories.map((story, i) => (
                    <div key={i} className="space-y-1">
                      <p className="font-bold text-gray-900 dark:text-white text-sm">
                        {story.priority} {i + 1}. {story.title}
                      </p>
                      <p className="text-indigo-500 dark:text-indigo-400 text-xs">📡 {story.source}</p>
                      <p className="text-gray-600 dark:text-gray-300 text-sm">{story.summary}</p>
                      <p className="text-violet-600 dark:text-violet-400 text-xs italic">🧠 {story.context}</p>
                      <p className="text-emerald-600 dark:text-emerald-400 text-xs">💡 {story.impact}</p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-gray-100 dark:border-gray-700 mt-4 pt-3 text-gray-400 dark:text-gray-500 text-xs text-center">
                  🎙️ Voice note below ⬇️
                </div>
              </div>

              {/* Voice note */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl p-4 shadow-sm border border-gray-100 dark:border-gray-700 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-indigo-600 dark:bg-indigo-500 flex items-center justify-center shrink-0">
                  <Mic2 className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1">
                  <div className="flex gap-1 items-end h-8">
                    {Array.from({ length: 28 }, (_, i) => (
                      <div
                        key={i}
                        className="w-1 bg-indigo-400 dark:bg-indigo-600 rounded-full opacity-70"
                        style={{ height: `${Math.random() * 28 + 4}px` }}
                      />
                    ))}
                  </div>
                </div>
                <span className="text-gray-400 dark:text-gray-500 text-xs shrink-0">3:12</span>
              </div>
            </div>
          </div>
      </ContainerScroll>
    </section>
  );
}

const faqs = [
  {
    q: "Is this completely free?",
    a: "Yes. The bot is free to use. No credit card, no subscription, no hidden fees.",
  },
  {
    q: "How do I subscribe?",
    a: "Just click the 'Subscribe on Telegram' button, then tap START on the bot. That's it — you're in.",
  },
  {
    q: "What time will I receive the digest?",
    a: "You choose! When you first start the bot, you can pick 7:00 AM, 8:00 AM, or 9:00 AM as your daily delivery time. You can also choose between English and Hindi.",
  },
  {
    q: "What sources does it pull from?",
    a: "OpenAI Blog, Google AI Blog, Microsoft AI, Meta AI Engineering, ArXiv ML, Hacker News, VentureBeat AI, TechCrunch AI, and Ars Technica.",
  },
  {
    q: "What languages are supported?",
    a: "English and Hindi. You choose your language when you first start the bot. The full digest text and voice briefing are delivered in your chosen language — no Hinglish mixing.",
  },
  {
    q: "Can I unsubscribe?",
    a: "Yes, send /stop to the bot at any time and you will never hear from us again.",
  },
];

export function FAQSection() {
  return (
    <section id="faq" className="py-16 md:py-24 bg-gray-50 dark:bg-gray-900">
      <div className="mx-auto max-w-2xl px-6">
        <div className="space-y-12">
          <FadeInSection>
            <div className="text-center">
              <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-sm uppercase tracking-wider mb-3 block">
                FAQ
              </span>
              <h2 className="text-gray-900 dark:text-white text-4xl font-bold">Your questions answered</h2>
            </div>
          </FadeInSection>

          <FadeInSection delay={0.1}>
            <Accordion
              type="single"
              collapsible
              className="-mx-2 sm:mx-0">
              {faqs.map((item, i) => (
                <div
                  className="group"
                  key={i}>
                  <AccordionItem
                    value={`item-${i}`}
                    className="data-[state=open]:bg-white dark:data-[state=open]:bg-gray-800 peer rounded-xl border-none px-5 py-1 data-[state=open]:border-none md:px-7 transition-colors">
                    <AccordionTrigger className="cursor-pointer text-left text-base hover:no-underline text-gray-900 dark:text-white font-semibold">
                      {item.q}
                    </AccordionTrigger>
                    <AccordionContent>
                      <p className="text-base text-gray-500 dark:text-gray-400 mt-2">{item.a}</p>
                    </AccordionContent>
                  </AccordionItem>
                  <hr className="mx-5 -mb-px group-last:hidden peer-data-[state=open]:opacity-0 md:mx-7 border-gray-200 dark:border-gray-800 transition-opacity" />
                </div>
              ))}
            </Accordion>
          </FadeInSection>
        </div>
      </div>
    </section>
  );
}

export function CTASection() {
  return (
    <section className="py-24 bg-indigo-600 dark:bg-indigo-950">
      <div className="container mx-auto px-6">
        <FadeInSection>
          <div className="text-center">
            <ShieldCheck className="w-12 h-12 text-indigo-300 dark:text-indigo-800 mx-auto mb-6" />
            <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Start your mornings smarter
            </h2>
            <p className="text-indigo-200 text-lg mb-8 max-w-md mx-auto">
              Join developers, researchers, and curious minds who
              stay ahead of AI — in 3 minutes a day. In English or Hindi.
            </p>
            <a
              href="https://t.me/aitechdigest_bot"
              target="_blank"
              rel="noopener noreferrer"
            >
              <button className="inline-flex items-center gap-3 bg-white dark:bg-gray-900 text-indigo-700 dark:text-white font-bold px-8 py-4 rounded-full text-lg shadow-lg hover:scale-105 hover:shadow-xl transition-all duration-200">
                <Send className="w-5 h-5" />
                Subscribe on Telegram — It's Free
              </button>
            </a>
            <p className="text-indigo-300 dark:text-indigo-600 text-sm mt-4">
              No spam · Unsubscribe with /stop · Forever free
            </p>
          </div>
        </FadeInSection>
      </div>
    </section>
  );
}
