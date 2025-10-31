# Deploying Hivemind to Railway

This guide walks you through deploying your Hivemind MCP server to Railway.

## Prerequisites

1. **GitHub account** - for code hosting
2. **Railway account** - sign up at [railway.app](https://railway.app)
3. **Google Cloud credentials** - your Firestore JSON key file
4. **Anthropic API key** - from [console.anthropic.com](https://console.anthropic.com)

## Step 1: Prepare Your Repository

### Push to GitHub

```bash
cd hivemind-mcp
git init
git add .
git commit -m "Initial commit - Hivemind MCP server"
git remote add origin https://github.com/YOUR_USERNAME/hivemind-mcp.git
git push -u origin main
```

### Important: Add Secrets to .gitignore

Make sure these are in your `.gitignore`:
```
*.pem
*.key
credentials.json
*-credentials.json
.env
.env.local
```

**NEVER commit your Google Cloud credentials or API keys to Git!**

## Step 2: Deploy to Railway

### Option A: Deploy via Railway Dashboard (Recommended)

1. Go to [railway.app/new](https://railway.app/new)
2. Click "Deploy from GitHub repo"
3. Connect your GitHub account
4. Select your `hivemind-mcp` repository
5. Railway will auto-detect the Dockerfile and start building

### Option B: Deploy via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Link to your GitHub repo
railway link

# Deploy
railway up
```

## Step 3: Configure Environment Variables

In the Railway dashboard, go to your project > Variables tab and add:

### Required Variables:

```
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
GOOGLE_APPLICATION_CREDENTIALS_JSON=<paste your entire credentials JSON file contents>
PORT=8080
```

### How to add Google credentials:

Since Railway doesn't support file uploads, we need to pass the JSON as an environment variable:

1. Open your `hivemind-476519-XXXXX.json` file
2. Copy the ENTIRE contents
3. In Railway Variables, create `GOOGLE_APPLICATION_CREDENTIALS_JSON`
4. Paste the entire JSON content as the value

### Optional Variables:

```
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

## Step 4: Get Your Deployment URL

After deployment completes:

1. Railway will provide a URL like: `https://hivemind-mcp-production-XXXX.up.railway.app`
2. Your MCP endpoint will be: `https://YOUR-RAILWAY-URL.up.railway.app/mcp/sse`

Test it by visiting: `https://YOUR-RAILWAY-URL.up.railway.app/health`

You should see: `{"status": "healthy"}`

## Step 5: Connect Claude Desktop

Update your Claude Desktop custom connector config:

**On Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**On macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hivemind": {
      "url": "https://YOUR-RAILWAY-URL.up.railway.app/mcp/sse",
      "transport": "sse"
    }
  }
}
```

Restart Claude Desktop and you should see the Hivemind tools available!

## Step 6: Monitor Your Deployment

Railway provides:
- **Logs**: Real-time application logs
- **Metrics**: CPU, memory, network usage
- **Deployments**: History of all deployments

Access these in the Railway dashboard for your project.

## Automatic Deployments

Railway automatically deploys on every push to your main branch!

```bash
# Make changes
git add .
git commit -m "Update privacy templates"
git push

# Railway will automatically rebuild and redeploy
```

## Troubleshooting

### Build Fails

- Check Railway logs for error messages
- Ensure `requirements.txt` is up to date
- Verify Dockerfile syntax

### Server Won't Start

- Check environment variables are set correctly
- Verify Google credentials JSON is valid
- Check Railway logs for startup errors

### MCP Connection Fails

- Ensure `/health` endpoint returns 200 OK
- Verify `/mcp/sse` endpoint is accessible
- Check Claude Desktop config JSON is valid
- Restart Claude Desktop after config changes

### Database Errors

- Verify `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set
- Check Firestore permissions in Google Cloud Console
- Ensure your service account has Firestore access

## Costs

Railway Pricing (as of 2024):
- **Free tier**: $5/month credit (plenty for testing!)
- **Hobby plan**: $5/month for more resources
- **Pro plan**: $20/month for production workloads

Your MCP server should easily fit in the free tier for development/testing.

## Security Best Practices

1. **Never commit secrets** - always use environment variables
2. **Use service accounts** - don't use your personal Google credentials
3. **Enable CORS carefully** - only allow trusted origins
4. **Monitor logs** - watch for suspicious activity
5. **Rotate keys** - periodically refresh API keys and credentials

## Next Steps

- Set up custom domain (Railway supports this!)
- Add monitoring/alerting
- Set up staging environment
- Configure backup strategy for Firestore

## Support

- Railway docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Hivemind issues: https://github.com/YOUR_USERNAME/hivemind-mcp/issues
