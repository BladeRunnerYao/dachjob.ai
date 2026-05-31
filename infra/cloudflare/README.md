# dachjob.ai — Cloudflare Free-Tier Deployment

This document contains step-by-step instructions for deploying dachjob.ai entirely on Cloudflare's free tier.

## Architecture

```text
┌─────────────────────┐     ┌──────────────────────────┐
│  Cloudflare Pages   │     │   Cloudflare Worker API  │
│  (Next.js static)   │────▶│   (Hono + TypeScript)    │
│  app.dachjob.ai     │     │   api.dachjob.ai         │
└─────────────────────┘     └──────────┬───────────────┘
                                       │
                            ┌──────────┴───────────────┐
                            │                          │
                     ┌──────▼──────┐          ┌───────▼───────┐
                     │ Cloudflare  │          │  Cloudflare   │
                     │     D1      │          │      R2       │
                     │ (SQLite DB) │          │ (File Storage)│
                     └─────────────┘          └───────────────┘
```

## Prerequisites

- A Cloudflare account (free plan)
- Node.js >= 20 installed locally
- `npm` package manager
- `wrangler` CLI (`npm install -g wrangler`)

## One-Time Setup

### 1. Authenticate Wrangler

```bash
wrangler login
```

This opens a browser to authorize the Wrangler CLI with your Cloudflare account.

### 2. Create D1 Database

```bash
wrangler d1 create dachjob-db
```

**Save the output** — you'll need the `database_id`. It looks like:
```
✅ Successfully created DB 'dachjob-db'
database_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### 3. Update wrangler.toml with Database ID

Edit `infra/cloudflare/worker-api/wrangler.toml`:
```toml
[[d1_databases]]
binding = "DB"
database_name = "dachjob-db"
database_id = "YOUR_DATABASE_ID_HERE"  # ← paste from step 2
```

### 4. Create R2 Bucket

```bash
wrangler r2 bucket create dachjob-storage
```

### 5. Run Database Migrations

```bash
cd infra/cloudflare/worker-api

# Test locally first
npx wrangler d1 execute dachjob-db --local --file=../migrations/0001_initial.sql

# Apply to production
npx wrangler d1 execute dachjob-db --remote --file=../migrations/0001_initial.sql
```

### 6. Set Secrets

```bash
cd infra/cloudflare/worker-api

# JWT signing key (generate a strong random string)
echo "$(openssl rand -hex 32)" | npx wrangler secret put JWT_SECRET

# DeepSeek API key
echo "your-deepseek-api-key" | npx wrangler secret put LLM_API_KEY

# Optional: override the default model (deepseek-v4-flash)
echo "deepseek-v4-flash" | npx wrangler secret put DEEPSEEK_MODEL
```

### 7. Deploy Worker API

```bash
cd infra/cloudflare/worker-api
npm ci
npx wrangler deploy
```

After deployment, note the Worker URL (e.g., `https://dachjob-api.your-subdomain.workers.dev`).

### 8. Configure Custom Domain (Optional)

In the Cloudflare dashboard:
1. Go to **Workers & Pages** → your worker → **Settings** → **Triggers**
2. Add a custom domain: `api.dachjob.ai`
3. Uncomment the routes line in `wrangler.toml`:
   ```toml
   routes = [{ pattern = "api.dachjob.ai", custom_domain = true }]
   ```

### 9. Deploy Frontend to Cloudflare Pages

```bash
cd app/frontend

# Set the API URL environment variable
export NEXT_PUBLIC_API_BASE_URL="https://api.dachjob.ai"
# Or use the workers.dev URL: https://dachjob-api.your-subdomain.workers.dev

npm ci
npm run build

# Deploy the static export to Pages
npx wrangler pages deploy out --project-name=dachjob-web
```

On first deploy, Wrangler will create the Pages project. Subsequent deploys update it.

### 10. Configure Frontend Custom Domain (Optional)

In the Cloudflare dashboard:
1. Go to **Workers & Pages** → `dachjob-web` → **Custom domains**
2. Add: `app.dachjob.ai`

## Environment Variables

### Worker API (`wrangler.toml` [vars])

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment name | `production` |
| `JWT_EXPIRY_HOURS` | Token lifetime in hours | `72` |
| `CORS_ORIGIN` | Allowed frontend origin(s) | `https://app.dachjob.ai` |

### Worker API Secrets (set via `wrangler secret put`)

| Secret | Description |
|--------|-------------|
| `JWT_SECRET` | HMAC key for JWT signing (min 32 chars) |
| `LLM_API_KEY` | DeepSeek API key |
| `DEEPSEEK_MODEL` | Optional DeepSeek model override; defaults to `deepseek-v4-flash` |

### Frontend (build-time environment)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Full URL to Worker API |

## Local Development

### Worker API

```bash
cd infra/cloudflare/worker-api
npm ci

# Create local D1 database and run migrations
npx wrangler d1 execute dachjob-db --local --file=../migrations/0001_initial.sql

# Start local dev server (uses local D1 + R2)
npx wrangler dev
```

The API runs at `http://localhost:8787`.

### Frontend

```bash
cd app/frontend
npm ci
NEXT_PUBLIC_API_BASE_URL=http://localhost:8787 npm run dev
```

The frontend runs at `http://localhost:3000`.

## iOS App Configuration

Update the API server URL in the iOS app to point to your Worker:

1. Open `ios/DachJob/Views/LoginView.swift`
2. Update the default server URL to `https://api.dachjob.ai` (or your workers.dev URL)

Alternatively, users can set the API URL in the iOS app's Settings screen.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/me` | Current user info |
| POST | `/api/jobs` | Create job |
| GET | `/api/jobs` | List jobs |
| GET | `/api/jobs/:id` | Get job |
| DELETE | `/api/jobs/:id` | Delete job |
| POST | `/api/profiles` | Create profile |
| GET | `/api/profiles` | List profiles |
| GET | `/api/profiles/:id` | Get profile |
| DELETE | `/api/profiles/:id` | Delete profile |
| POST | `/api/match` | Match profile against job |
| POST | `/api/resumes/generate` | Generate tailored CV |
| POST | `/api/artifacts/upload` | Upload file |
| GET | `/api/artifacts/:id` | Download artifact |
| GET | `/api/artifacts` | List artifacts |
| DELETE | `/api/artifacts/:id` | Delete artifact |

## Free Tier Limits (Cloudflare)

| Service | Free Tier Limit | Notes |
|---------|----------------|-------|
| Workers | 100,000 requests/day | More than enough for single-user |
| D1 | 5 million rows read/day, 100k writes/day | Very generous |
| R2 | 10 GB storage, 10 million reads/month | Plenty for resumes |
| Pages | Unlimited sites, 500 builds/month | Automatic |

## Troubleshooting

### CORS errors
Update `CORS_ORIGIN` in `wrangler.toml` to match your actual frontend domain.

### JWT errors
Ensure `JWT_SECRET` is set via `wrangler secret put` (not in wrangler.toml).

### D1 "no such table" errors
Run migrations: `npx wrangler d1 execute dachjob-db --remote --file=../migrations/0001_initial.sql`

### LLM not working
Ensure `LLM_API_KEY` is set to a DeepSeek API key. The app defaults to `deepseek-v4-flash` and gracefully degrades (returns fallback results) when LLM is unavailable.

## CI/CD (GitHub Actions)

For automated deploys, create `.github/workflows/deploy-cloudflare.yml`:

```yaml
name: Deploy to Cloudflare
on:
  push:
    branches: [feature/cloudflare_deployment]

jobs:
  deploy-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
        working-directory: infra/cloudflare/worker-api
      - run: npx wrangler deploy
        working-directory: infra/cloudflare/worker-api
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
        working-directory: app/frontend
      - run: npm run build
        working-directory: app/frontend
        env:
          NEXT_PUBLIC_API_BASE_URL: https://api.dachjob.ai
      - run: npx wrangler pages deploy out --project-name=dachjob-web
        working-directory: app/frontend
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

Set `CLOUDFLARE_API_TOKEN` in your GitHub repository secrets. Generate the token in Cloudflare dashboard → My Profile → API Tokens → Create Token → "Edit Cloudflare Workers" template.

## Cost Summary

| Component | Monthly Cost |
|-----------|-------------|
| Cloudflare Workers | €0 (free tier) |
| Cloudflare D1 | €0 (free tier) |
| Cloudflare R2 | €0 (under 10 GB) |
| Cloudflare Pages | €0 (free) |
| **Total** | **€0/month** |
