# Front-End Architecture — Trading Intelligence

## Purpose

Establish the first user-facing workspace for the capabilities currently present in MASTER ARSENAL: Binance opening analysis, closing analysis, intraday market analysis, and skills audit.

The first interface is intentionally limited to Trading Intelligence. It is not a promise of future modules that have not been implemented.

## Technology

- React for the component model and interactive UI.
- TypeScript for typed components, data contracts, and application flows.
- JavaScript remains a first-class option for small utilities and modules where static typing is not useful.
- Vite for the development server and production asset build.
- Hand-authored CSS for the initial design system.

The TypeScript configuration enables `allowJs`; JavaScript and TypeScript can coexist in the same source tree.

## Repository boundary

The application lives in `frontend/`. It is developed independently from the Python packages:

- `binance_data_engine/`
- `local_engine/`
- `report_engine/`

The browser UI must not access the local filesystem, MALE workspace files, or Python modules directly. Runtime communication will be introduced through a documented local API/bridge contract in a later integration step.

## Initial navigation scope

- Dashboard
- Market Intelligence
- Skills Management
- Job Center
- Approvals
- Execution History
- Reports
- Settings

Navigation items are currently presentation scaffolding. They must not be presented as operational until their screens and actions are implemented.

## Data integrity and UX rules

- Demo values must be visibly identified as demo/preview data.
- Missing provider data must not be represented as zero or as a healthy/live state.
- Market data must expose source and freshness when real integration is added.
- Job actions must preserve MALE's validate/approve/run lifecycle and approval requirements.
- The UI must not bypass approval gates or add order execution/trading functionality.
- Reports must only be shown as available when the backend confirms the artifact exists.

## Development

See [frontend/README.md](../frontend/README.md) for Codespaces and local commands.
