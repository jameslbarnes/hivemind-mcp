# Hivemind Remote MCP Connector Setup

This guide shows how to run Hivemind as a **custom connector** that works remotely with Claude.

## What is a Custom Connector?

Custom connectors let you connect Claude to your own MCP servers via HTTP/SSE. This means:
- ✅ Works remotely (not just local stdio)
- ✅ Can be shared across multiple Claude instances
- ✅ Can run on a server accessible from anywhere
- ✅ Test locally first with `localhost` URL

## Requirements

- Claude **Pro**, **Max**, **Team**, or **Enterprise** plan (custom connectors are in beta)
- Python 3.10+
- The dependencies in `requirements_remote.txt`

## Quick Start (Local Testing)

### 1. Install Dependencies

```bash
pip install -r requirements_remote.txt
```

### 2. Start the Remote MCP Server

```bash
python src/remote_mcp_server.py
```

You should see:
```
======================================================================
HIVEMIND REMOTE MCP SERVER (Custom Connector)
======================================================================

Starting server...
Local URL: http://localhost:8080/mcp/sse
Health check: http://localhost:8080/health

To use as custom connector:
1. Start this server
2. In Claude, go to Settings > Connectors
3. Click 'Add custom connector'
4. Enter: http://localhost:8080/mcp/sse
5. Click 'Add'
```

### 3. Test the Server

In a new terminal:

```bash
python test_remote_connector.py
```

This verifies the server is responding correctly.

### 4. Add to Claude as Custom Connector

**For Pro and Max Plans:**
1. In Claude, go to **Settings > Connectors**
2. Click **"Add custom connector"**
3. Enter your connector URL: `http://localhost:8080/mcp/sse`
4. (Optional) Configure OAuth in Advanced settings if needed
5. Click **"Add"**

**For Team and Enterprise Plans:**
1. As Primary Owner/Owner, go to **Admin settings > Connectors**
2. Select **"Add custom connector"**
3. Input the URL: `http://localhost:8080/mcp/sse`
4. Configure OAuth if needed
5. Click **"Add"**

### 5. Use in Claude

Once added, you'll see the connector in your chat:
1. Click the **"Search and tools"** button in Claude
2. You should see "Hivemind Remote MCP" in the connectors list
3. Enable it
4. Start using the tools!

Try:
```
User: Create a space called "Test Space" with type "public"

Claude: [calls create_space tool]
```

## Available Tools

The remote connector provides these tools:

1. **log_conversation_turn** - Log conversations and route through policies
2. **create_space** - Create new spaces (1:1, group, or public)
3. **list_spaces** - View all your spaces
4. **join_space** - Join a space with an invite code
5. **read_space** - Read context from a space

## Remote Deployment (Production)

To make this accessible from anywhere (not just localhost):

### Option 1: Deploy to a Cloud Server

1. **Deploy to a server** (AWS, GCP, Azure, DigitalOcean, etc.)

2. **Use a proper domain with HTTPS** (required for production):
   ```bash
   # Example with nginx reverse proxy
   server {
       listen 443 ssl;
       server_name mcp.yourdomain.com;

       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;

       location /mcp/ {
           proxy_pass http://localhost:8080/mcp/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Update the connector URL in Claude**:
   ```
   https://mcp.yourdomain.com/mcp/sse
   ```

### Option 2: Use ngrok for Testing

For quick remote testing without deploying:

```bash
# Install ngrok
# Start your local server
python src/remote_mcp_server.py

# In another terminal
ngrok http 8080
```

Then use the ngrok URL (e.g., `https://abc123.ngrok.io/mcp/sse`) in Claude.

⚠️ **Note**: ngrok URLs change each time, so this is only for testing.

### Option 3: Deploy to Fly.io (Easy)

1. Install flyctl: https://fly.io/docs/hands-on/install-flyctl/

2. Create `fly.toml`:
   ```toml
   app = "hivemind-mcp"

   [build]

   [http_service]
     internal_port = 8080
     force_https = true
   ```

3. Deploy:
   ```bash
   fly launch
   fly deploy
   ```

4. Use URL in Claude:
   ```
   https://hivemind-mcp.fly.dev/mcp/sse
   ```

## OAuth Support (Optional)

The server includes basic OAuth endpoints at:
- `/oauth/authorize` - Authorization page
- `/oauth/token` - Token exchange

To configure OAuth in Claude:
1. When adding the connector, click **Advanced settings**
2. Enter:
   - **Client ID**: `your-client-id`
   - **Client Secret**: `your-client-secret`
3. The server will handle the OAuth flow

⚠️ **Note**: The current implementation is a demo. For production, implement proper OAuth with:
- Real user authentication
- Secure token storage
- Token expiration/refresh

## Troubleshooting

### "Cannot connect to server"
- Make sure the server is running: `python src/remote_mcp_server.py`
- Check firewall settings
- Verify the URL is correct

### "Invalid connector URL"
- Make sure the URL includes `/mcp/sse` at the end
- Use `http://` for local testing
- Use `https://` for remote deployment (required)

### "Tools not showing in Claude"
- Make sure the connector is enabled in the chat
- Click "Search and tools" button to enable connectors
- Refresh the page

### CORS errors (in browser console)
- The server has CORS enabled by default
- If still having issues, check your reverse proxy settings

## Security Notes

⚠️ **Important for Production:**

1. **Always use HTTPS** for remote deployments
2. **Implement proper authentication** (OAuth or API keys)
3. **Validate all user inputs** before processing
4. **Rate limit** requests to prevent abuse
5. **Store secrets securely** (use environment variables)
6. **Review the Claude docs**: https://support.claude.com/en/articles/11175166

## Differences from Local MCP

| Feature | Local MCP (stdio) | Remote MCP (HTTP/SSE) |
|---------|-------------------|------------------------|
| Transport | stdio | HTTP with SSE |
| Connection | Direct process | HTTP requests |
| Configuration | Claude Code settings | Custom connector URL |
| Access | Local only | Can be remote |
| Auth | Not needed | OAuth supported |
| CORS | N/A | Required for web |

## Architecture

```
Claude (Web/Desktop)
      ↓ HTTP/SSE
Remote MCP Server (Flask + SSE)
      ↓
Space Manager + Policy Engine
      ↓
Firestore / Local Storage
```

## Next Steps

1. ✅ Test locally with `localhost` URL
2. ✅ Verify tools work in Claude
3. Deploy to a remote server (optional)
4. Set up OAuth for multi-user support (optional)
5. Add monitoring and logging
6. Implement TEE-based policy execution

## Resources

- [Claude Custom Connectors Docs](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)
- [MCP Documentation](https://modelcontextprotocol.io)
- [MCP SSE Transport](https://github.com/modelcontextprotocol/python-sdk)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the Claude docs on custom connectors
- Check MCP documentation for SSE transport details
