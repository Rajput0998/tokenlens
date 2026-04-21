# Web Dashboard

The TokenLens dashboard provides a real-time web interface for monitoring token usage.

## Starting the Dashboard

```bash
tokenlens serve --ui --port 7890
```

Open `http://localhost:7890` in your browser.

## Pages

### Command Center (Home)
- Live token counter with animated updates
- Multi-color burn rate gauge (green → yellow → orange → red)
- Per-tool status cards with real hourly sparkline data
- Smart alert banner
- 3D animated InfoTooltips with numbered tips on all sections
- Premium dark/light theme with Inter + JetBrains Mono fonts

### Analytics
- Token usage timeline (stacked area chart)
- Tool comparison bar chart
- Model usage pie chart
- Token intensity heatmap (24×7)
- Session list with expandable details

### Insights
- Burn rate forecast with confidence bands
- Cost projection
- Efficiency trends
- Anomaly timeline
- What-if simulator
- Behavioral profile card

### How It Works
- Interactive explainer page at `/how-it-works`
- 3 tabs: Claude Code, Kiro, How Tokens Work
- Claude Code tab: data collection pipeline, what gets tracked (input/output/cache tokens), cost calculation formula with examples, 5-hour rolling window session detection with visual timeline
- Kiro tab: MCP-based data collection, tiktoken estimation, gap-based session detection
- How Tokens Work tab: token basics, input vs output pricing, cache token economics, burn rate categories
- Collapsible sections with smooth animations, formula blocks, and flow step visualizations

### Settings
- Tool configuration
- Budget limits
- Alert thresholds
- Plan selector (Pro / Max5 / Max20 / Custom)
- Model pricing table with cache rates
- Data management
