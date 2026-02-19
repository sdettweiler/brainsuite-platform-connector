# Deploying on Replit

## Step-by-step guide

### 1. Import this repo into Replit

Go to [replit.com](https://replit.com) → **Create Repl** → **Import from GitHub** → paste your repo URL.

Or click: **+ Create** → **Import from GitHub**.

---

### 2. Create a PostgreSQL database

1. In your Repl, open the **Database** tab (left sidebar, cylinder icon)
2. Click **Create a database** → select **PostgreSQL**
3. Replit will automatically set a `DATABASE_URL` secret — your app reads this automatically

---

### 3. Set Secrets (Environment Variables)

In your Repl, go to **Tools → Secrets** and add:

| Secret Key | Value | Required |
|---|---|---|
| `SECRET_KEY` | Run `openssl rand -hex 32` locally | ✅ Yes |
| `TOKEN_ENCRYPTION_KEY` | Run `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | ✅ Yes |
| `META_APP_ID` | From Facebook Developer portal | Only if using Meta |
| `META_APP_SECRET` | From Facebook Developer portal | Only if using Meta |
| `META_REDIRECT_URI` | `https://YOUR-REPL-URL/api/v1/platforms/oauth/callback/meta` | Only if using Meta |
| `TIKTOK_APP_ID` | From TikTok Business API portal | Only if using TikTok |
| `TIKTOK_APP_SECRET` | From TikTok Business API portal | Only if using TikTok |
| `TIKTOK_REDIRECT_URI` | `https://YOUR-REPL-URL/api/v1/platforms/oauth/callback/tiktok` | Only if using TikTok |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console | Only if using YouTube |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console | Only if using YouTube |
| `GOOGLE_REDIRECT_URI` | `https://YOUR-REPL-URL/api/v1/platforms/oauth/callback/google` | Only if using YouTube |
| `GOOGLE_DEVELOPER_TOKEN` | From Google Ads account | Only if using YouTube |
| `EXCHANGE_RATE_API_KEY` | From exchangerate-api.com (free tier ok) | Optional |

> **Your Repl URL** looks like: `https://brainsuite-platform-connector.yourusername.repl.co`
> Find it by clicking the **Open in new tab** button at the top of Replit.

---

### 4. Run the app

Click the **Run** button (▶). On first run it will:
1. Install Python dependencies (~2 min)
2. Run database migrations
3. Build the Angular frontend (~3-4 min)
4. Start the FastAPI server

**Subsequent runs** are much faster since the frontend is already built.

---

### 5. Access the app

- **App:** `https://YOUR-REPL-URL` (the Angular frontend)
- **API docs:** `https://YOUR-REPL-URL/docs` (Swagger UI — only in DEBUG mode)
- **Health check:** `https://YOUR-REPL-URL/health`

---

## Important Notes

### Always-on (paid feature)
Replit free tier **sleeps** after inactivity. For a production app, upgrade to **Replit Core** or use **Always On** to keep it running. Alternatively, use a free uptime service like UptimeRobot to ping your `/health` endpoint every 5 minutes.

### Memory
Free Replit repls have ~512MB RAM. This app needs ~400-500MB. If you hit memory errors:
- Reduce uvicorn workers (already set to 1 in the startup script)
- Use Replit's paid tier (1GB+ RAM)

### Persistent storage
Replit's filesystem **resets on redeploy** — but your PostgreSQL database is persistent. All data synced from platforms is safe in the database.

### Build time
The Angular build takes 3-4 minutes on first run. After that, the `dist/` folder persists and subsequent starts are fast.

### OAuth redirect URIs
Make sure to update your OAuth app settings with the Replit URL. See `PLATFORM_SETUP.md` for detailed instructions per platform.

---

## Troubleshooting

**"No DATABASE_URL found"**
→ Create a PostgreSQL database in the Replit Database tab.

**"Module not found" errors**
→ The pip install may have been interrupted. Click Run again.

**Frontend shows blank page**
→ The Angular build may have failed. Check the console for errors. Try deleting `frontend/dist/` and running again.

**"CORS error" in browser**
→ Add your Repl URL to the `BACKEND_CORS_ORIGINS` secret: `["https://YOUR-REPL-URL"]`

**App is slow on first load**
→ The Repl woke up from sleep. It'll be fast once warmed up.
