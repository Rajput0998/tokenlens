import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Info, X, Lightbulb, Sparkles } from "lucide-react";

interface InfoTooltipProps {
  title: string;
  description: string;
  tips?: string[];
}

export function InfoTooltip({ title, description, tips }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const [animating, setAnimating] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const pw = 320;
      const ph = 320;
      let top = rect.bottom + 10;
      let left = rect.right - pw;
      if (left + pw > window.innerWidth - 20) left = window.innerWidth - pw - 20;
      if (left < 20) left = 20;
      if (top + ph > window.innerHeight - 20) top = rect.top - ph - 10;
      if (top < 20) top = Math.max(20, (window.innerHeight - ph) / 2);
      setPos({ top, left });
      // Trigger animation
      requestAnimationFrame(() => setAnimating(true));
    } else {
      setAnimating(false);
    }
  }, [open]);

  const handleClose = () => {
    setAnimating(false);
    setTimeout(() => setOpen(false), 200);
  };

  return (
    <div className="inline-block">
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        className="group p-1 rounded-full transition-all duration-200 text-muted-foreground/40 hover:text-[var(--teal)] hover:bg-[var(--teal-dim)] hover:scale-110"
        aria-label={`Info about ${title}`}
      >
        <Info className="h-3.5 w-3.5 transition-transform group-hover:rotate-12" />
      </button>

      {open &&
        createPortal(
          <>
            {/* Backdrop with blur */}
            <div
              className="fixed inset-0 z-[9998] transition-all duration-200"
              style={{
                backgroundColor: animating ? "rgba(0,0,0,0.2)" : "transparent",
                backdropFilter: animating ? "blur(2px)" : "none",
              }}
              onClick={handleClose}
            />

            {/* Popover with 3D animation */}
            <div
              className="fixed z-[9999] w-80"
              style={{
                top: pos.top,
                left: pos.left,
                transform: animating
                  ? "perspective(800px) rotateX(0deg) scale(1) translateY(0)"
                  : "perspective(800px) rotateX(-8deg) scale(0.92) translateY(-8px)",
                opacity: animating ? 1 : 0,
                transition: "all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)",
                transformOrigin: "top center",
              }}
            >
              {/* Glow effect behind card */}
              <div
                className="absolute -inset-1 rounded-2xl opacity-30 blur-lg"
                style={{ background: "var(--gradient-primary)" }}
              />

              {/* Card */}
              <div className="relative rounded-2xl border bg-card overflow-hidden"
                style={{ boxShadow: "0 8px 32px rgba(0,0,0,0.2), 0 0 0 1px hsl(var(--border))" }}
              >
                {/* Header with gradient accent line */}
                <div className="h-1" style={{ background: "var(--gradient-primary)" }} />

                <div className="p-5">
                  {/* Title row */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 rounded-lg" style={{ background: "var(--teal-dim)" }}>
                        <Sparkles className="h-4 w-4" style={{ color: "var(--teal)" }} />
                      </div>
                      <h4 className="text-sm font-bold leading-tight">{title}</h4>
                    </div>
                    <button
                      onClick={handleClose}
                      className="p-1 rounded-lg hover:bg-muted text-muted-foreground transition-colors flex-shrink-0"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {/* Description — formatted with line breaks for readability */}
                  <p className="text-[13px] text-muted-foreground leading-[1.7]">
                    {description}
                  </p>

                  {/* Tips section */}
                  {tips && tips.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-dashed space-y-2.5">
                      <div className="flex items-center gap-1.5">
                        <Lightbulb className="h-3 w-3" style={{ color: "var(--orange)" }} />
                        <p className="text-[10px] font-bold uppercase tracking-[1.5px]" style={{ color: "var(--orange)" }}>
                          Pro Tips
                        </p>
                      </div>
                      {tips.map((tip, i) => (
                        <div key={i} className="flex gap-2.5 items-start">
                          <span
                            className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold mt-0.5"
                            style={{
                              background: "var(--teal-dim)",
                              color: "var(--teal)",
                            }}
                          >
                            {i + 1}
                          </span>
                          <p className="text-xs text-muted-foreground leading-relaxed">{tip}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>,
          document.body
        )}
    </div>
  );
}
