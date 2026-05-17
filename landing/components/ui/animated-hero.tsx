"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { MoveRight, Send } from "lucide-react";
import { Button } from "@/components/ui/button";

function Hero() {
  const [titleNumber, setTitleNumber] = useState(0);
  const titles = useMemo(
    () => ["noise", "hype", "scrolling", "clutter", "FOMO"],
    []
  );

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setTitleNumber((prev) => (prev === titles.length - 1 ? 0 : prev + 1));
    }, 2000);
    return () => clearTimeout(timeoutId);
  }, [titleNumber, titles]);

  return (
    <div className="w-full min-h-screen flex items-center bg-linear-to-br from-white via-blue-50 to-indigo-50 dark:from-gray-950 dark:via-gray-900 dark:to-indigo-950">
      <div className="container mx-auto px-6">
        <div className="flex gap-8 py-20 lg:py-32 items-center justify-center flex-col">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Button
              variant="secondary"
              size="sm"
              className="gap-3 bg-indigo-100 text-indigo-700 hover:bg-indigo-200 border-0 rounded-full px-5 py-2 font-medium"
            >
              Now available on Telegram <MoveRight className="w-4 h-4" />
            </Button>
          </motion.div>

          {/* Headline */}
          <div className="flex gap-4 flex-col items-center">
            <motion.h1
              className="text-5xl md:text-7xl max-w-3xl tracking-tight text-center font-bold text-gray-900 dark:text-white"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
            >
              <span>Stay on top of AI</span>
              <br />
              <span>Without the </span>
              <span className="relative inline-flex w-full justify-center overflow-hidden text-center pb-2 pt-1">
                &nbsp;
                {titles.map((title, index) => (
                  <motion.span
                    key={index}
                    className="absolute font-extrabold text-indigo-600 dark:text-indigo-400"
                    initial={{ opacity: 0, y: 80 }}
                    transition={{ type: "spring", stiffness: 60 }}
                    animate={
                      titleNumber === index
                        ? { y: 0, opacity: 1 }
                        : { y: titleNumber > index ? -80 : 80, opacity: 0 }
                    }
                  >
                    {title}
                  </motion.span>
                ))}
              </span>
            </motion.h1>

            <motion.p
              className="text-lg md:text-xl leading-relaxed text-gray-500 dark:text-gray-400 max-w-2xl text-center mt-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.2 }}
            >
              Everything you need, nothing you don't. Built by a developer for people who care about AI but don't have time to doomscroll tech Twitter. Your daily 3-minute audio briefing, delivered straight to Telegram.
            </motion.p>
          </div>

          {/* CTA Buttons */}
          <motion.div
            className="flex flex-col sm:flex-row items-center justify-center w-full sm:w-auto gap-4 mt-2 px-4 sm:px-0"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
          >
            <a
              href="https://t.me/aitechdigest_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto"
            >
              <Button
                size="lg"
                className="w-full sm:w-auto gap-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full px-8 py-3 text-base font-semibold shadow-lg shadow-indigo-200 transition-all hover:scale-105"
              >
                <Send className="w-5 h-5" />
                Subscribe on Telegram
              </Button>
            </a>
            <a href="#how-it-works" className="w-full sm:w-auto">
              <Button
                size="lg"
                variant="outline"
                className="w-full sm:w-auto gap-3 rounded-full px-8 py-3 text-base font-semibold border-gray-300 text-gray-700 hover:border-indigo-400 hover:text-indigo-700 dark:border-gray-700 dark:text-gray-300 dark:hover:text-indigo-400 dark:hover:border-indigo-500"
              >
                See how it works <MoveRight className="w-4 h-4" />
              </Button>
            </a>
          </motion.div>

          {/* Social Proof */}
          <motion.p
            className="text-sm text-gray-400 mt-2 text-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            Free forever · No spam · Unsubscribe anytime
          </motion.p>
        </div>
      </div>
    </div>
  );
}

export { Hero };
