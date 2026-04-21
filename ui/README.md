# TokenLens Dashboard

React + TypeScript + Vite frontend for the TokenLens token usage intelligence platform.

## Development

```bash
npm install
npm run dev      # Start dev server with HMR
npm run test     # Run tests (Vitest)
npm run build    # Production build → dist/
```

## Build Integration

`npm run build` outputs to `dist/`. The FastAPI backend serves these static files:

```bash
tokenlens serve --ui   # Mounts dist/ via FastAPI StaticFiles at localhost:7890
```

No Node.js is required at runtime — the frontend ships as pre-built static files.

## Stack

- **React 18** + TypeScript (strict)
- **TailwindCSS v3** + shadcn/ui (CSS variables, dark mode)
- **Zustand** — state management
- **TanStack Query v5** — server state / data fetching
- **React Router** — client-side routing (/, /analytics, /insights, /settings)
- **Recharts** — charts (area, bar, pie)
- **D3.js** — heatmap only
- **Lucide React** — icons
- **Vitest** + Testing Library — tests
