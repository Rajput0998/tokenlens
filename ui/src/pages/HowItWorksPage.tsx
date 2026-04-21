import { useState } from "react";
import {
  FileText, Cpu, Zap, ArrowRight, Database, Brain,
  Terminal, Code2, Sparkles, Calculator, DollarSign,
  Clock, Layers, ChevronDown, ChevronUp,
} from "lucide-react";

type ToolTab = "claude_code" | "kiro" | "general";

const TOOL_TABS: { id: ToolTab; label: string; icon: typeof Cpu; color: string }[] = [
  { id: "claude_code", label: "Claude Code", icon: Terminal, color: "var(--teal)" },
  { id: "kiro", label: "Kiro", icon: Sparkles, color: "var(--blue)" },
  { id: "general", label: "How Tokens Work", icon: Brain, color: "var(--purple)" },
];

function AnimatedNumber({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="text-center p-4 rounded-xl border bg-card shadow-card hover:shadow-card-hover transition-all hover:-translate-y-0.5">
      <p className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>{value}</p>
      <p className="text-[10px] uppercase tracking-[1px] text-muted-foreground mt-1 font-semibold">{label}</p>
    </div>
  );
}

function FormulaBlock({ formula, description, example }: { formula: string; description: string; example?: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-card space-y-3">
      <div className="rounded-lg p-4 font-mono text-sm leading-relaxed overflow-x-auto"
        style={{ background: "var(--teal-dim)", color: "var(--teal)" }}>
        {formula}
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      {example && (
        <div className="rounded-lg p-3 bg-muted/50 border border-dashed">
          <p className="text-[10px] uppercase tracking-[1px] text-muted-foreground font-semibold mb-1">Example</p>
          <p className="text-xs font-mono text-muted-foreground">{example}</p>
        </div>
      )}
    </div>
  );
}

function FlowStep({ step, title, description, icon: Icon, color, isLast }: {
  step: number; title: string; description: string; icon: typeof Cpu; color: string; isLast?: boolean;
}) {
  return (
    <div className="flex gap-4">
      {/* Vertical line + circle */}
      <div className="flex flex-col items-center">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold shadow-card"
          style={{ background: color, color: "#fff" }}>
          {step}
        </div>
        {!isLast && <div className="w-0.5 flex-1 my-1" style={{ background: `${color}33` }} />}
      </div>
      {/* Content */}
      <div className="pb-6 flex-1">
        <div className="flex items-center gap-2 mb-1">
          <Icon className="h-4 w-4" style={{ color }} />
          <h4 className="font-semibold text-sm">{title}</h4>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

function CollapsibleSection({ title, icon: Icon, color, children, defaultOpen = false }: {
  title: string; icon: typeof Cpu; color: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border bg-card shadow-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: `${color}20` }}>
            <Icon className="h-5 w-5" style={{ color }} />
          </div>
          <h3 className="font-semibold">{title}</h3>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>
      <div
        style={{
          maxHeight: open ? "2000px" : "0",
          opacity: open ? 1 : 0,
          transition: "max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease",
          overflow: "hidden",
        }}
      >
        <div className="px-5 pb-5 space-y-4">{children}</div>
      </div>
    </div>
  );
}

function ClaudeCodeSection() {
  return (
    <div className="space-y-6">
      {/* Data Flow */}
      <CollapsibleSection title="Data Collection Pipeline" icon={Database} color="var(--teal)" defaultOpen>
        <p className="text-sm text-muted-foreground mb-4">
          Claude Code writes every conversation turn to JSONL log files. TokenLens watches these files in real-time and parses each entry.
        </p>
        <FlowStep step={1} title="Claude Code writes JSONL" icon={FileText} color="var(--teal)"
          description="Every API response is logged to ~/.claude/projects/**/*.jsonl with exact token counts from Anthropic's API." />
        <FlowStep step={2} title="Daemon watches with OS events" icon={Zap} color="var(--teal)"
          description="TokenLens daemon uses inotify (Linux) or FSEvents (macOS) to detect file changes in <100ms. No polling." />
        <FlowStep step={3} title="Incremental parsing" icon={Code2} color="var(--teal)"
          description="Only new lines are read using byte-offset tracking. The daemon remembers where it left off — never re-reads old data." />
        <FlowStep step={4} title="Store in SQLite" icon={Database} color="var(--teal)"
          description="Events are batched, deduplicated (by file+offset), enriched with cost, and flushed to SQLite with WAL mode for concurrent access." isLast />
      </CollapsibleSection>

      {/* Token Fields */}
      <CollapsibleSection title="What Gets Tracked" icon={Layers} color="var(--blue)">
        <p className="text-sm text-muted-foreground mb-4">
          Each JSONL entry from Claude Code contains these exact fields from Anthropic's API:
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <AnimatedNumber value="input" label="Prompt tokens" color="var(--blue)" />
          <AnimatedNumber value="output" label="Response tokens" color="var(--purple)" />
          <AnimatedNumber value="cache_w" label="Cache creation" color="var(--teal)" />
          <AnimatedNumber value="cache_r" label="Cache read" color="var(--green)" />
        </div>
        <p className="text-xs text-muted-foreground mt-3">
          These are <strong>exact counts</strong> from Anthropic's API — not estimates. Every token is accounted for.
        </p>
      </CollapsibleSection>

      {/* Cost Formula */}
      <CollapsibleSection title="Cost Calculation" icon={Calculator} color="var(--orange)">
        <FormulaBlock
          formula="cost = (input × input_rate + output × output_rate + cache_create × create_rate + cache_read × read_rate) / 1,000,000"
          description="Cost is calculated per-model using Anthropic's published pricing. Cache tokens have separate rates — creation costs 1.25× the input rate, reads cost 0.1× the input rate."
          example="1000 input × $3.00 + 500 output × $15.00 + 200 cache_create × $3.75 + 300 cache_read × $0.30 = $0.01185"
        />
        <div className="grid grid-cols-3 gap-3 mt-3">
          <AnimatedNumber value="$3.00" label="Sonnet input/M" color="var(--blue)" />
          <AnimatedNumber value="$15.00" label="Opus input/M" color="var(--purple)" />
          <AnimatedNumber value="$0.80" label="Haiku input/M" color="var(--green)" />
        </div>
      </CollapsibleSection>

      {/* Session Detection */}
      <CollapsibleSection title="Session Detection" icon={Clock} color="var(--purple)">
        <p className="text-sm text-muted-foreground mb-4">
          Claude Code uses a <strong>5-hour rolling window</strong> model. A session starts at your first message and expires exactly 5 hours later.
        </p>
        <FormulaBlock
          formula="session_active = (event.timestamp >= session.start) AND (event.timestamp < session.start + 5 hours)"
          description="Events within the 5-hour window are grouped into the same session. After 5 hours, a new session starts. Multiple sessions can overlap."
        />
        {/* Visual timeline */}
        <div className="rounded-lg p-4 bg-muted/30 border">
          <p className="text-[10px] uppercase tracking-[1px] text-muted-foreground font-semibold mb-3">Session Timeline Example</p>
          <div className="relative h-12">
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-muted" />
            {/* Session A */}
            <div className="absolute top-2 left-[5%] w-[40%] h-6 rounded-md flex items-center px-2"
              style={{ background: "var(--teal-dim)", border: "1px solid var(--teal)" }}>
              <span className="text-[10px] font-mono font-bold" style={{ color: "var(--teal)" }}>Session A (10:00 → 15:00)</span>
            </div>
            {/* Session B - overlapping */}
            <div className="absolute top-2 left-[30%] w-[40%] h-6 rounded-md flex items-center px-2"
              style={{ background: "var(--blue-dim)", border: "1px solid var(--blue)", top: "2.5rem" }}>
              <span className="text-[10px] font-mono font-bold" style={{ color: "var(--blue)" }}>Session B (12:00 → 17:00)</span>
            </div>
          </div>
          <div className="flex justify-between text-[9px] text-muted-foreground font-mono mt-8">
            <span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>18:00</span>
          </div>
        </div>
      </CollapsibleSection>
    </div>
  );
}

function KiroSection() {
  return (
    <div className="space-y-6">
      <CollapsibleSection title="Data Collection via MCP" icon={Sparkles} color="var(--blue)" defaultOpen>
        <p className="text-sm text-muted-foreground mb-4">
          Kiro doesn't write log files like Claude Code. Instead, TokenLens runs as an <strong>MCP server</strong> that Kiro calls directly.
        </p>
        <FlowStep step={1} title="MCP tool call" icon={Zap} color="var(--blue)"
          description="When a hook fires, Kiro calls log_conversation_turn() on the TokenLens MCP server via stdio transport." />
        <FlowStep step={2} title="Token estimation via tiktoken" icon={Brain} color="var(--blue)"
          description="Since Kiro doesn't expose actual token counts, we estimate using tiktoken's cl100k_base encoding — the same tokenizer used by Claude models." />
        <FlowStep step={3} title="Role-based classification" icon={Layers} color="var(--blue)"
          description="role='user' → counted as input tokens. role='assistant' → counted as output tokens. This determines cost split." />
        <FlowStep step={4} title="Store in SQLite" icon={Database} color="var(--blue)"
          description="Events are stored with estimated=true metadata flag so you know these are estimates, not exact API counts." isLast />
      </CollapsibleSection>

      <CollapsibleSection title="Token Estimation" icon={Calculator} color="var(--orange)">
        <FormulaBlock
          formula={'tokens = tiktoken.get_encoding("cl100k_base").encode(text).length'}
          description="We use OpenAI's tiktoken library with the cl100k_base encoding (same family as Claude's tokenizer). If tiktoken isn't installed, falls back to ~4 characters per token."
          example='"Hello, how are you?" → tiktoken encodes to 6 tokens'
        />
        <div className="rounded-lg p-4 bg-muted/30 border mt-3">
          <p className="text-[10px] uppercase tracking-[1px] font-semibold mb-2" style={{ color: "var(--orange)" }}>⚠️ Important Limitation</p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            The MCP hook only sees the text explicitly passed to it — <strong>not</strong> the full context window (system prompts, steering files, tool results). 
            Real token consumption is higher than what TokenLens reports for Kiro. The <code className="bg-muted px-1 rounded text-[11px]">estimated: true</code> flag marks these events.
          </p>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Session Detection" icon={Clock} color="var(--purple)">
        <FormulaBlock
          formula="new_session = (event.timestamp - last_event.timestamp) > 15 minutes"
          description="Kiro uses gap-based session detection. If there's more than 15 minutes of silence between events, a new session starts. A gap of exactly 15 minutes does NOT trigger a new session (strictly greater than)."
        />
      </CollapsibleSection>
    </div>
  );
}

function GeneralSection() {
  return (
    <div className="space-y-6">
      <CollapsibleSection title="What is a Token?" icon={Brain} color="var(--purple)" defaultOpen>
        <p className="text-sm text-muted-foreground leading-relaxed mb-4">
          A <strong>token</strong> is the smallest unit of text that an AI model processes. It's not exactly a word — it's a piece of a word, a whole word, or even punctuation. On average, <strong>1 token ≈ 4 characters</strong> in English.
        </p>
        <div className="grid grid-cols-3 gap-3">
          <AnimatedNumber value="1 tok" label='"Hello"' color="var(--teal)" />
          <AnimatedNumber value="3 tok" label='"artificial"' color="var(--blue)" />
          <AnimatedNumber value="~750" label="words per 1K tokens" color="var(--purple)" />
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Input vs Output Tokens" icon={ArrowRight} color="var(--teal)">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border p-4 space-y-2" style={{ borderColor: "var(--blue)" }}>
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg" style={{ background: "var(--blue-dim)" }}>
                <ArrowRight className="h-4 w-4" style={{ color: "var(--blue)" }} />
              </div>
              <h4 className="font-semibold text-sm">Input Tokens</h4>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Everything you send TO the model: your prompt, file contents, system instructions, conversation history, tool results. This is usually the larger portion.
            </p>
            <p className="text-lg font-bold font-mono" style={{ color: "var(--blue)" }}>$3.00/M</p>
            <p className="text-[10px] text-muted-foreground">Sonnet 4 pricing</p>
          </div>
          <div className="rounded-xl border p-4 space-y-2" style={{ borderColor: "var(--purple)" }}>
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg" style={{ background: "var(--purple)" + "20" }}>
                <ArrowRight className="h-4 w-4 rotate-180" style={{ color: "var(--purple)" }} />
              </div>
              <h4 className="font-semibold text-sm">Output Tokens</h4>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Everything the model sends BACK: code, explanations, tool calls. Output tokens are 5× more expensive than input tokens.
            </p>
            <p className="text-lg font-bold font-mono" style={{ color: "var(--purple)" }}>$15.00/M</p>
            <p className="text-[10px] text-muted-foreground">Sonnet 4 pricing (5× input)</p>
          </div>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Cache Tokens" icon={Zap} color="var(--green)">
        <p className="text-sm text-muted-foreground mb-4">
          When you send the same context repeatedly (like a large file), Claude caches it. Subsequent reads from cache are <strong>90% cheaper</strong> than re-processing.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <FormulaBlock
            formula="cache_creation = input_rate × 1.25"
            description="First time a context is cached. Slightly more expensive than regular input (25% premium)."
            example="Sonnet: $3.00 × 1.25 = $3.75/M"
          />
          <FormulaBlock
            formula="cache_read = input_rate × 0.10"
            description="Reading from an existing cache. 90% cheaper than regular input — this is where you save money."
            example="Sonnet: $3.00 × 0.10 = $0.30/M"
          />
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Burn Rate & Limits" icon={DollarSign} color="var(--orange)">
        <FormulaBlock
          formula="burn_rate = total_tokens_today / hours_elapsed_since_midnight"
          description="Tokens consumed per hour, averaged across the day. Used to predict when you'll hit your daily limit."
        />
        <div className="grid grid-cols-4 gap-3 mt-3">
          <AnimatedNumber value="<1K/hr" label="Slow" color="var(--green)" />
          <AnimatedNumber value="1-5K/hr" label="Normal" color="var(--blue)" />
          <AnimatedNumber value="5-10K/hr" label="Fast" color="var(--orange)" />
          <AnimatedNumber value=">10K/hr" label="Critical" color="var(--red)" />
        </div>
      </CollapsibleSection>
    </div>
  );
}

export function HowItWorksPage() {
  const [activeTab, setActiveTab] = useState<ToolTab>("claude_code");

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold">How It Works</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Understand how TokenLens calculates tokens, costs, and sessions for each tool.
        </p>
      </div>

      {/* Tool tabs */}
      <div className="flex gap-2 p-1 rounded-xl bg-muted/50 border">
        {TOOL_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all duration-200"
              style={{
                background: isActive ? "var(--teal-dim)" : "transparent",
                color: isActive ? tab.color : "var(--muted-foreground)",
                boxShadow: isActive ? "var(--shadow-card)" : "none",
                transform: isActive ? "scale(1.02)" : "scale(1)",
              }}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content with animation */}
      <div
        key={activeTab}
        style={{
          animation: "fadeSlideIn 0.3s ease-out",
        }}
      >
        {activeTab === "claude_code" && <ClaudeCodeSection />}
        {activeTab === "kiro" && <KiroSection />}
        {activeTab === "general" && <GeneralSection />}
      </div>

      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
