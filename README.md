# Threads Killer

Multi-account Threads posting bot controlled via Telegram. Posts recur every 15 minutes until you pause via Telegram command.

## How it works

1. Send posts to the Telegram bot (`/add acc1 <text>`)
2. Cron triggers posting every 15 minutes
3. Posts keep looping until you say `/cooldown acc1`
4. Resume anytime with `/resume acc1`

## Telegram Commands

| Command | Description |
|---|---|
| `/add <acc> <text>` | Add post to queue |
| `/edit <acc> <id> <text>` | Edit a post |
| `/remove <acc> <id>` | Remove a post |
| `/list <acc>` | List all posts |
| `/status [acc]` | Show queue size, cooldown state |
| `/cooldown <acc\|all>` | Pause posting |
| `/resume <acc\|all>` | Resume posting |

## Deploy to Vercel (free, no credit card)

### 1. Create a GitHub Gist for storage

1. Go to https://gist.github.com
2. Create a new file named `queues.json` with content: `{}`
3. Create another file named `cooldowns.json` with content: `{}`
4. Click **Create public gist**
5. Copy the Gist ID from the URL: `https://gist.github.com/username/GIST_ID_HERE`

### 2. Get a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scope: **gist** (read/write)
4. Copy the token

### 3. Deploy to Vercel

1. Push your repo to GitHub
2. Go to https://vercel.com, sign in with GitHub
3. Import your repo
4. In **Environment Variables**, add:
   ```
   TELEGRAM_BOT_TOKEN = your_bot_token
   THREADS_ACCESS_TOKEN_ACC1 = your_token
   THREADS_USER_ID_ACC1 = your_user_id
   GIST_ID = your_gist_id
   GITHUB_TOKEN = your_github_token
   ```
5. Deploy

### 4. Set up Telegram Webhook

After deployment, Vercel gives you a URL like `https://your-app.vercel.app`. Run this command to set the webhook:

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://your-app.vercel.app/api/webhook"
```

### 5. Set up cronjob.org (posts every 15 min)

1. Go to https://cronjob.org, create free account
2. Add new job:
   - URL: `https://your-app.vercel.app/api/trigger`
   - Method: POST
   - Schedule: every 15 minutes
3. Save

### 6. Set up UptimeRobot (keeps function warm)

1. Go to https://uptimerobot.com, create free account
2. Add New Monitor > HTTP(s)
3. URL: `https://your-app.vercel.app/api/health`
4. Interval: 5 minutes

## Local Development

```bash
pip install requests
export TELEGRAM_BOT_TOKEN=your_token
export THREADS_ACCESS_TOKEN_ACC1=token
export THREADS_USER_ID_ACC1=user_id
export GIST_ID=your_gist_id
export GITHUB_TOKEN=your_github_token
python -m http.server 3000 --directory api
```

## Project Structure

```
api/index.py       - Vercel serverless function (all endpoints)
storage.py         - GitHub Gist-based storage
threads_api.py     - Threads API posting logic
config.py          - Configuration
vercel.json        - Vercel deploy config
```
