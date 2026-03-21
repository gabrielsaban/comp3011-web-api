# RouteWise UK Frontend

Next.js frontend for the COMP3011 road-risk API.

## Product Name

**RouteWise UK**

A practical journey-risk web interface that wraps the API into three user-facing workflows:

- Route Planner (`/planner`): waypoint input -> route-risk score + segment breakdown
- Insights (`/insights`): annual trend, weather correlation, and hotspot lookup
- Developer Console (`/developer`): quick endpoint probe with JSON response viewer

## Local Run

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Frontend default URL: `http://localhost:3000`

## Environment Variables

Set in `frontend/.env.local` (local) or Vercel project env vars (cloud):

```bash
NEXT_PUBLIC_API_BASE_URL=https://comp3011-web-api-production.up.railway.app
```

## Vercel Deployment

1. Import this repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Add `NEXT_PUBLIC_API_BASE_URL`.
4. Deploy.

## Backend CORS Reminder

Railway API must allow your Vercel origin:

```bash
CORS_ALLOW_ORIGINS=https://<your-vercel-project>.vercel.app
```
