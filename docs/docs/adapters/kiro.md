# Kiro Adapter

Kiro integration uses the Model Context Protocol (MCP) for real-time token logging.

## Setup

Add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "tokenlens": {
      "command": "tokenlens",
      "args": ["mcp-serve"]
    }
  }
}
```

## MCP Tools

- `log_conversation_turn` — Log a conversation turn with token estimation
- `get_token_status` — Get today's usage summary
- `get_efficiency_tips` — Get optimization recommendations

## Steering File

When enabled, TokenLens auto-generates `.kiro/steering/token-budget.md` every 30 minutes with current usage data and tips.
