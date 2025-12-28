# Fly.io Deployment Guide

This guide will walk you through deploying your Telegram bot to Fly.io for free.

## Prerequisites

1. A Fly.io account (sign up at https://fly.io/app/sign-up)
2. Fly CLI installed on your machine
3. Your environment variables ready (API keys)

## Step 1: Install Fly CLI

### macOS
```bash
brew install flyctl
```

### Linux
```bash
curl -L https://fly.io/install.sh | sh
```

### Windows
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

## Step 2: Authenticate with Fly.io

```bash
fly auth login
```

This will open a browser window for authentication.

## Step 3: Launch Your App

From your project directory, run:

```bash
fly launch
```

When prompted:
1. **App name**: Accept the suggested name or choose your own (e.g., `telegram-knowledge-bot`)
2. **Region**: Choose a region close to you or your users (e.g., `sin` for Singapore)
3. **Do you want to set up a Postgresql database?**: Choose **No**
4. **Do you want to set up an Upstash Redis database?**: Choose **No**
5. **Would you like to deploy now?**: Choose **No** (we need to set secrets first)

Note: The `fly.toml` file already exists in your project, so Fly.io will use it.

## Step 4: Create Persistent Volume for SQLite Database

Create a volume to store your SQLite database:

```bash
fly volumes create bot_data --region sin --size 1
```

Replace `sin` with your chosen region if different.

## Step 5: Set Environment Variables (Secrets)

Set your sensitive environment variables as secrets:

```bash
fly secrets set OPENROUTER_API_KEY=your_openrouter_api_key
fly secrets set FIRECRAWL_API_KEY=your_firecrawl_api_key
fly secrets set PARALLEL_API_KEY=your_parallel_api_key
fly secrets set OPENROUTER_MODEL=minimax/minimax-m2.1
fly secrets set DB_PATH=/data/bot.db
```

Replace the values with your actual API keys from your `.env` file.

## Step 6: Deploy Your Bot

Now deploy your application:

```bash
fly deploy
```

This will:
- Build your Docker image
- Push it to Fly.io
- Create and start your machine
- Mount the persistent volume at `/data`

## Step 7: Verify Deployment

Check if your app is running:

```bash
fly status
```

View logs to ensure the bot started correctly:

```bash
fly logs
```

## Monitoring and Management

### View Real-time Logs
```bash
fly logs -f
```

### SSH into Your Machine
```bash
fly ssh console
```

### Check Machine Status
```bash
fly machine list
```

### Scale Your App (if needed)
```bash
# Increase memory
fly scale memory 512

# Add more machines
fly scale count 2
```

## Updating Your Bot

When you make changes to your code:

1. Commit your changes to git
2. Deploy the update:
   ```bash
   fly deploy
   ```

## Stopping Your Bot

To stop your bot without deleting it:

```bash
fly machine stop <machine-id>
```

To start it again:

```bash
fly machine start <machine-id>
```

## Destroying Your App

If you want to completely remove your app:

```bash
fly apps destroy <app-name>
```

## Troubleshooting

### Bot not responding
1. Check logs: `fly logs`
2. Verify secrets are set: `fly secrets list`
3. Check machine status: `fly status`

### Database errors
1. Ensure volume is mounted: `fly volumes list`
2. Check DB_PATH is set to `/data/bot.db`
3. SSH into machine and verify: `fly ssh console` then `ls -la /data`

### Out of memory
1. Check current usage: `fly status`
2. Increase memory: `fly scale memory 512`

## Free Tier Limits

Fly.io free tier includes:
- Up to 3 shared-cpu VMs with 256MB RAM each
- 3GB persistent storage total
- 160GB outbound data transfer per month

Your bot should comfortably fit within these limits.

## Cost Optimization Tips

1. Use `auto_stop_machines = false` in fly.toml to keep bot running 24/7
2. Monitor usage with `fly machine status`
3. Keep memory at 256MB unless you experience issues
4. Use a single machine (already configured)

## Support

- Fly.io Docs: https://fly.io/docs
- Fly.io Community: https://community.fly.io
- Check logs first: `fly logs`
