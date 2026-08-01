# Beyblade Stock Tracker

Checks https://www.toysrus.com.my/beyblade/ every 15 minutes and pings your
Telegram the moment a product flips from "unavailable" to in stock.

## 1. Create a Telegram bot (2 min)

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, follow the prompts, name it whatever
3. BotFather gives you a **bot token** — looks like `123456789:AAExxxxxxx` — save it
4. Send your new bot any message (e.g. "hi") so it knows you exist
5. Get your **chat ID**: open this URL in a browser (replace `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Look for `"chat":{"id":123456789,...}` — that number is your chat ID

## 2. Create a GitHub repo and push this code

```bash
cd beyblade-tracker
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Keep the repo **public** — GitHub Actions minutes are unlimited for public
repos. If you want it private, you get 2000 free minutes/month, which is
plenty at a 15-min check interval (~2880 runs/month × ~15 sec each).

## 3. Add your secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

- `TELEGRAM_BOT_TOKEN` = the token from step 1
- `TELEGRAM_CHAT_ID` = the chat ID from step 1

## 4. Test it

Go to the **Actions** tab → "Check Beyblade availability" → **Run workflow**
(manual trigger). Check the run logs — it should say "Found 88 products"
(or however many are listed) and "No new availability" on the first run,
since it has nothing to compare against yet.

After that, it runs automatically every 15 minutes and only messages you
when something actually comes back in stock.

## Notes / things that could break this

- **If TRU changes their site's HTML structure**, the scraper might stop
  finding products. The script exits with an error (and won't overwrite
  state.json) if it finds zero products on a run — check the Actions logs
  if you stop getting expected notifications.
- **First run has no baseline**, so it won't notify on anything already
  in stock at that moment — only on changes from that point forward.
- 15 minutes is a balance between "fast enough" and not hammering their
  server. You can lower the cron interval, but GitHub doesn't reliably
  honor anything under ~5 min on the free tier anyway (schedule runs get
  queued/delayed under load).
