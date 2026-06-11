# Trendscout Frontend

Next.js 16 + Tailwind UI for the trendscout backend: a Schüco-style **Trendradar**,
newsfeed/dashboard and an expert-review surface for the trends produced by the
pipeline.

## Prerequisites

- Node.js 20+
- The backend running on `:8000` (see `../backend/README.md`)

## Commands

```bash
npm install
npm run dev        # dev server on :3000
npm run lint       # ESLint
npm run typecheck  # tsc --noEmit
npm run build      # production build
```

## Configuration

Copy `.env.example` to `.env.local`. `NEXT_PUBLIC_API_BASE` points at the backend
(default `http://127.0.0.1:8000`); `NEXT_PUBLIC_API_TOKEN` must match the backend
`API_TOKEN` for state-changing requests (leave empty for local dev).

## Layout

```
src/app/        pages: page (search), newsfeed, radar, trends/[id]
src/components/ shared UI
src/lib/        api.ts (backend client), i18n.tsx (de/en)
```

See `AGENTS.md` for the Next.js 16 caveat before doing frontend work.
