"use client";

import { motion } from "motion/react";
import { useState, useRef, useCallback, useEffect, CSSProperties } from "react";

type CurtainPhase = "idle" | "prepare" | "animating";
type Theme = "light" | "dark";

const EASING = "cubic-bezier(0.76, 0, 0.24, 1)";
const DURATION = 1200;

export function LightPullThemeSwitcher() {
    const [theme, setTheme] = useState<Theme>("light");
    const [phase, setPhase] = useState<CurtainPhase>("idle");
    const curtainColorRef = useRef<string>("#ffffff");
    const transformOriginRef = useRef<"top" | "bottom">("bottom");

    // Sync with global Tailwind dark class on mount
    useEffect(() => {
      if (typeof document !== "undefined") {
        const isDark = document.documentElement.classList.contains("dark");
        setTheme(isDark ? "dark" : "light");
      }
    }, []);

    const toggleDarkMode = useCallback(() => {
        if (phase !== "idle") return;
        const root = document.documentElement;
        
        if (theme === "light") {
            // Light -> Dark: 
            // We put a LIGHT solid overlay that shrinks down to the bottom.
            // This reveals the DARK UI sliding down from the ceiling.
            curtainColorRef.current = "#ffffff";
            transformOriginRef.current = "bottom";
            setPhase("prepare");
            
            setTimeout(() => {
                setTheme("dark");
                root.classList.add("dark");
                setPhase("animating");
                
                setTimeout(() => {
                    setPhase("idle");
                }, DURATION);
            }, 20); // allow reflow for scaleY(1)
            
        } else {
            // Dark -> Light:
            // We put a DARK solid overlay that shrinks up to the ceiling.
            // This reveals the LIGHT UI underneath as if the dark curtain rolls up.
            curtainColorRef.current = "#030712";
            transformOriginRef.current = "top";
            setPhase("prepare");
            
            setTimeout(() => {
                setTheme("light");
                root.classList.remove("dark");
                setPhase("animating");
                
                setTimeout(() => {
                    setPhase("idle");
                }, DURATION);
            }, 20);
        }
    }, [phase, theme]);

    let curtainTransform = "scaleY(0)";
    let curtainTransition = "none";

    if (phase === "prepare") {
        curtainTransform = "scaleY(1)";
        curtainTransition = "none";
    } else if (phase === "animating") {
        curtainTransform = "scaleY(0)";
        curtainTransition = `transform ${DURATION}ms ${EASING}`;
    }

    const curtainStyle: CSSProperties = {
        position: "fixed",
        inset: 0,
        backgroundColor: curtainColorRef.current,
        transformOrigin: transformOriginRef.current,
        transform: curtainTransform,
        transition: curtainTransition,
        zIndex: 9997,
        pointerEvents: "none",
    };

    return (
      <>
        {/* Cinematic Curtain Overlay */}
        <div aria-hidden="true" style={curtainStyle} />

        {/* Pull Cord */}
        <div className="relative h-56 w-24 flex justify-center pointer-events-auto z-9998">
          <motion.div
            animate={{ rotate: [-3, 3] }}
            transition={{
              repeat: Infinity,
              repeatType: "reverse",
              duration: 2,
              ease: "easeInOut",
            }}
            style={{ transformOrigin: "center -500px" }}
            className="absolute inset-0 w-full h-full flex justify-center"
          >
            <motion.div
              drag="y"
              dragDirectionLock
              onDragEnd={(event, info) => {
                // Trigger toggle if pulled down far enough
                if (info.offset.y > 20) {
                  toggleDarkMode();
                }
              }}
              dragConstraints={{ top: 0, right: 0, bottom: 0, left: 0 }}
              dragTransition={{ bounceStiffness: 500, bounceDamping: 15 }}
              dragElastic={0.075}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              whileDrag={{ cursor: "grabbing" }}
              className="absolute top-16 w-12 h-12 rounded-full cursor-grab
                   bg-[radial-gradient(circle_at_center,#facc15,#fcd34d,#fef9c3)] 
                   dark:bg-[radial-gradient(circle_at_center,#64748b,#334155,#0f172a)] 
                   shadow-[0_0_30px_12px_rgba(250,204,21,0.6)] 
                   dark:shadow-[0_0_30px_10px_rgba(148,163,184,0.4)]
                   border-2 border-yellow-200 dark:border-slate-500"
            >
              {/* The actual string */}
              <div className="absolute bottom-12 left-1/2 -translate-x-1/2 w-1 h-[9999px] bg-neutral-300 dark:bg-slate-600 shadow-sm"></div>
            </motion.div>
          </motion.div>
        </div>
      </>
    );
}
