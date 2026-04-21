import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "../home/InfoTooltip";
import { formatLocalDateTime } from "@/lib/dateUtils";

export interface SessionTurn {
  turnNumber: number;
  inputTokens: number;
  outputTokens: number;
  contextSize: number;
  cacheHit: boolean;
}

export interface SessionData {
  id: string;
  tool: string;
  startTime: string;
  duration: string;
  totalTokens: number;
  turns: SessionTurn[];
  cacheRatio: number;
}

interface SessionListProps {
  sessions: SessionData[];
  loading?: boolean;
}

function SessionRow({ session }: { session: SessionData }) {
  const [expanded, setExpanded] = useState(false);

  const contextGrowth = session.turns.map((t) => ({ v: t.contextSize }));

  return (
    <>
      <tr
        className="border-b hover:bg-muted/50 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </td>
        <td className="px-3 py-2 text-sm font-mono">{session.id.slice(0, 8)}</td>
        <td className="px-3 py-2 text-sm">{session.tool}</td>
        <td className="px-3 py-2 text-sm">{formatLocalDateTime(session.startTime)}</td>
        <td className="px-3 py-2 text-sm">{session.duration}</td>
        <td className="px-3 py-2 text-sm tabular-nums">
          {session.totalTokens.toLocaleString()}
        </td>
        <td className="px-3 py-2 text-sm">{session.turns.length}</td>
        <td className="px-3 py-2 text-sm">{Math.round(session.cacheRatio * 100)}%</td>
        <td className="px-3 py-2 w-20">
          <ResponsiveContainer width="100%" height={20}>
            <LineChart data={contextGrowth}>
              <Line
                type="monotone"
                dataKey="v"
                stroke="hsl(var(--primary))"
                strokeWidth={1}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="px-6 py-3 bg-muted/30">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="text-left px-2 py-1">Turn</th>
                  <th className="text-left px-2 py-1">Input</th>
                  <th className="text-left px-2 py-1">Output</th>
                  <th className="text-left px-2 py-1">Context</th>
                  <th className="text-left px-2 py-1">Cache</th>
                </tr>
              </thead>
              <tbody>
                {session.turns.map((turn) => (
                  <tr key={turn.turnNumber} className="border-t border-muted">
                    <td className="px-2 py-1">#{turn.turnNumber}</td>
                    <td className="px-2 py-1 tabular-nums">
                      {turn.inputTokens.toLocaleString()}
                    </td>
                    <td className="px-2 py-1 tabular-nums">
                      {turn.outputTokens.toLocaleString()}
                    </td>
                    <td className="px-2 py-1 tabular-nums">
                      {turn.contextSize.toLocaleString()}
                    </td>
                    <td className="px-2 py-1">
                      <span
                        className={cn(
                          "inline-block h-2 w-2 rounded-full",
                          turn.cacheHit ? "bg-green-500" : "bg-muted-foreground/30"
                        )}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

export function SessionList({ sessions, loading }: SessionListProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-muted rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <p className="text-muted-foreground">No sessions recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">Sessions</h3>
          <InfoTooltip
            title="Session History"
            description="Each row is a coding session — a continuous period of AI tool usage. Click a row to expand and see individual turns (each message exchange). The context column shows how context size grew during the session."
            tips={[
              "Shorter sessions with fewer turns are usually more efficient",
              "High cache ratio means the AI is reusing context effectively",
              "Growing context column indicates context bloat — consider starting fresh",
              "Sessions are detected by 15-min gaps (gap-based) or 5-hour windows (Claude Code)",
            ]}
          />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="px-3 py-2 w-8" />
              <th className="px-3 py-2 text-left">ID</th>
              <th className="px-3 py-2 text-left">Tool</th>
              <th className="px-3 py-2 text-left">Start</th>
              <th className="px-3 py-2 text-left">Duration</th>
              <th className="px-3 py-2 text-left">Tokens</th>
              <th className="px-3 py-2 text-left">Turns</th>
              <th className="px-3 py-2 text-left">Cache</th>
              <th className="px-3 py-2 text-left">Context</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <SessionRow key={session.id} session={session} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
