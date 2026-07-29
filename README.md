# Threads Multi-Account Queue Dashboard

Manage 3 Threads accounts from one dashboard. Add posts whenever you want;
each account posts a burst of 10 every 30 minutes across a 12-hour daily
window (24 bursts x 10 = **240 posts/day/account**). Everything free: GitHub
repo as the database, GitHub Pages as the dashboard host, GitHub Actions as
the posting engine.

**Heads up on volume:** 240/day sits just under Threads' documented API cap
of 250 posts/24h per account, so it fits — but there's very little margin
for manual posts on top of it, and posting at that frequency may also read
as automated/spammy to Threads' own abuse systems independent of the API
limit, which could get an account rate-limited or restricted at the platform
level. If any of your 3 accounts is new or low-follower, consider starting
lower (e.g. edit `posts_per_burst` down in `accounts.json`) and watching how
it's treated before scaling up.

## How it fits together
- `queues/acc1.json`, `acc2.json`, `acc3.json` — each account's post queue,
  stored right in the repo
- `docs/index.html` — the dashboard (hosted free via GitHub Pages) where you
  add posts to any account's queue
- `.github/workflows/scheduler.yml` — runs every 15 min, publishes the next
  queued post for any account that's under its daily burst limit and past
  its cooldown
- `.github/workflows/refresh-tokens.yml` — keeps all 3 tokens alive weekly

## Setup

### 1. Get a long-lived token for EACH of your 3 accounts
Repeat the OAuth flow from `get_long_lived_token.py` (from the earlier
single-account version — reuse it) three times, once per Threads account/
tester. Each run gives you a token + user ID.

### 2. Push this repo to GitHub, enable Pages
```
git init && git add . && git commit -m "Threads dashboard"
git remote add origin <your-repo-url>
git push -u origin main
```
Repo → Settings → Pages → Source: **Deploy from a branch** → Branch: `main`
→ Folder: **/docs** → Save. GitHub gives you a URL like
`https://yourusername.github.io/your-repo/` — that's your dashboard.

### 3. Add repo secrets
Repo → Settings → Secrets and variables → Actions → New repository secret,
one pair per account:
- `THREADS_ACCESS_TOKEN_ACC1` / `THREADS_USER_ID_ACC1`
- `THREADS_ACCESS_TOKEN_ACC2` / `THREADS_USER_ID_ACC2`
- `THREADS_ACCESS_TOKEN_ACC3` / `THREADS_USER_ID_ACC3`
- `GH_PAT` — optional, only needed for the auto-refresh workflow (a personal
  access token with `repo` scope)

Rename the accounts if you want — edit the `label` fields in `accounts.json`
and the `ACCOUNTS` array at the top of `docs/index.html`'s `<script>` to
match (keep the `id`s like `acc1` consistent across both, since that's what
ties everything together).

### 4. Give the dashboard its own access
The dashboard writes directly to your repo via the GitHub API, so it needs
its own token:
- Go to github.com/settings/personal-access-tokens → **Fine-grained token**
- Repository access: only this repo
- Permissions: **Contents → Read and write**
- Copy the token

Open your dashboard URL → "connection settings" → enter your GitHub
username, repo name, branch (`main`), and paste that token. It's saved only
in your browser's local storage — never sent anywhere except `api.github.com`.

### 5. Use it
Open the dashboard on your phone or laptop anytime. Pick an account, type a
post, hit "Add to queue." The burst meter shows how many of today's 10 slots
are filled. The scheduler workflow picks up pending posts automatically —
you don't need to do anything else.

## The posting logic, precisely
Every 30 minutes, for each account:
1. Check if the current UTC hour is inside that account's active window
   (default `08:00`–`20:00` UTC, edit `active_start_hour_utc` /
   `active_end_hour_utc` in `accounts.json` per account, e.g. to offset
   accounts across different timezones)
2. If inside the window and there's anything pending in the queue, publish
   up to `posts_per_burst` (default 10) oldest-first, sleeping
   `seconds_between_posts_in_burst` (default 150s) between each — the whole
   burst takes ~22.5 min, comfortably inside the 30-min window before the
   next trigger

So with a queue of ~100 posts and 240/day going out, you'd burn through it
in under half a day if the window ran a full 12 hours with no gaps in
queued content — keep the dashboard topped up regularly, or reduce
`posts_per_burst` if that pace is more than you actually need.

## Notes
- Trigger `workflow_dispatch` manually from the Actions tab any time you
  want to test without waiting for the cron.
- If a post fails (bad token, rate limit, etc.) the error gets written into
  that item's `last_error` field in the queue JSON — visible if you peek at
  the file in the repo, not currently surfaced in the dashboard UI.
- A `concurrency` guard in the workflow prevents overlapping runs in case a
  burst runs long and bumps into the next 30-min trigger.
