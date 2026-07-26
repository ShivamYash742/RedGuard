# RedGuard 🛡️

RedGuard is a unified Next.js dashboard and FastAPI backend for autonomous red-teaming of LLM security, built on the Franklin et al. 2025 Google DeepMind AI Agent Traps taxonomy. 

It provides an interactive UI to run security scans, inspect adversarial probes, and generate comprehensive audit reports—all backed by a robust PostgreSQL database.

## Architecture

- **Frontend**: Next.js (React) + TailwindCSS for the interactive dashboard and unified scan execution.
- **Backend API**: FastAPI (Python) driving the core red-teaming logic.
- **Database**: PostgreSQL with Prisma ORM for tracking Sessions, Probe Events, and generated Reports.
- **DPI Proxy**: Python-based Inspector for monitoring prompts and responses.
- **ML Classifier**: Fine-tuned MiniLM (F1 0.970) for intent detection and adversarial classification.

## Attack Categories Covered (Franklin et al. 2025)

1. **Content Injection**: Hidden instructions embedded in tool outputs
2. **Semantic Manipulation**: Biased framing, role impersonation, authority spoofing
3. **Cognitive State**: Poisoned context injection, false memory
4. **Behavioural Control**: Embedded jailbreaks, data exfiltration attempts
5. **Systemic**: Rate-based congestion probes
6. **Human-in-the-Loop**: Approval fatigue generation, misleading summaries

## Quickstart

```bash
1. Clone the repository
   git clone https://github.com/yourusername/agenttrap
   cd agenttrap/redguard

2. Install dependencies
   npm install
   cd backend && pip install -r requirements.txt && cd ..

3. Set environment variables
   cp .env.example .env
   # Ensure GROQ_API_KEY and DATABASE_URL are set in your .env

4. Push database schema
   cd backend && npx prisma db push && cd ..

5. Run the application
   npm run dev:all
   # This starts both the Next.js frontend (port 3000) and FastAPI backend (port 8000)

6. Access the Dashboard
   Open http://localhost:3000 in your browser to run scans and view reports.
```

## Features

- **One-Click Scans**: Trigger full security scans against your LLM agents directly from the UI.
- **Live Stream**: Watch probes execute and receive real-time classification verdicts.
- **Audit Trails**: Generate and view detailed Markdown and JSON reports for regulatory compliance.
- **Coverage Gap Analysis**: Easily identify attacks that bypassed basic regex policies but were caught by the ML classifier.
# RedGuard
