# Frontend Workstation - AI-Driven Intelligent UFDR Analysis System

This directory contains the React application shell for the forensic investigation workstation.

## Architecture & Directory Layout

```
frontend/
├── src/
│   ├── components/          # Reusable forensic UI components (Header, Sidebar)
│   ├── layouts/             # Main application workstation layout
│   ├── pages/               # Forensic modules (PlaceholderPage and future views)
│   ├── services/
│   │   └── api/             # Centralized API client and HTTP error handling
│   ├── types/               # TypeScript interfaces (Navigation, API responses)
│   ├── utils/               # Navigation constants and helpers
│   ├── index.css            # Forensic dark theme & typography design system
│   ├── App.tsx              # Root application component
│   └── main.tsx             # Entrypoint
├── public/                  # Static assets
├── index.html               # Main HTML entrypoint
├── package.json             # NPM dependencies & scripts
├── tsconfig.json            # Strict TypeScript configuration
├── vite.config.ts           # Vite server, build, and API proxy configuration
└── README.md
```

## Local Development Setup

### 1. Install Node Dependencies
```bash
cd frontend
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The application will launch at `http://localhost:3000` with automated API proxying to `http://localhost:8000`.

### 3. Build Production Bundle
```bash
npm run build
```

## Navigation Modules in Phase 1
The Phase 1 shell provides the complete navigation taxonomy with active architectural specifications:
* **Core:** Dashboard, Cases, Evidence, Investigations
* **Forensic Analysis:** Search, Timeline, Communication Graph, Anomalies
* **Governance:** Reports, Audit Logs, Settings
