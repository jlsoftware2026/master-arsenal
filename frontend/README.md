# MASTER ARSENAL Front-End

React + TypeScript + JavaScript + Vite workspace for the Trading Intelligence desktop experience.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Run in GitHub Codespaces

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open forwarded port **5173** in the Codespaces Ports panel. The Vite server binds to `0.0.0.0` so the forwarded port is reachable from the browser.

## Available scripts

- `npm run dev` — start the development server.
- `npm run typecheck` — check TypeScript.
- `npm run build` — type-check and create a production build in `dist/`.
- `npm run preview` — preview the production build on port 4173.

## JavaScript and TypeScript

Both are supported. TypeScript is enabled for TS/TSX files; `allowJs` is enabled so JavaScript modules can be imported directly. Keep plain JavaScript where it is the clearer choice and use TypeScript where explicit contracts and component props add value.

## Current state

The dashboard is a visual foundation only. Its sample activity and summary values are mock/demo content, not live market data and not connected to MALE. The interface must not imply live connectivity until a real backend contract and integration are implemented.
