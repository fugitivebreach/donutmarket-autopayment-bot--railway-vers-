# Railway Deployment Guide

This guide will help you deploy the DonutMarket Autopayment Bot to Railway.

## Quick Deployment Steps

1. **Fork this repository** to your GitHub account

2. **Create a Railway account** at [railway.app](https://railway.app)

3. **Create a new project** from your GitHub repository:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your forked repository

4. **Add a MySQL Database** in Railway:
   - Click "New" → "Database" → "Add MySQL"
   - Railway will automatically create MYSQL_* environment variables

5. **Set Environment Variables** in Railway dashboard:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   DISCORD_CLIENT_ID=your_discord_client_id
   AUTHORIZED_USERS=your_user_id_here
   MINECRAFT_HOST=east.donutsmp.net
   MINECRAFT_PORT=25565
   MINECRAFT_USERNAME=your_minecraft_username
   MINECRAFT_TYPE=Java
   MINECRAFT_VERSION=1.21.5
   AUTH_TYPE=microsoft
   DONUTSMP_API_KEY=your_api_key
   AFK_ACCOUNTS={"SappedNap": "password1", "N4yzen": "password2", "DorDunutt": "password3"}
   AFK_HOST=east.donutsmp.net
   AFK_PORT=25565
   AFK_TYPE=java
   AFK_VERSION=1.21.5
   AFK_AUTH=microsoft
   ```
   
   **Note**: Do NOT set MINECRAFT_PASSWORD when using Microsoft authentication. The MySQL database will store authentication tokens automatically.

5. **Deploy**: Railway will automatically build and deploy your bot

## Configuration Files

The following files are configured for Railway deployment:

- `Procfile` - Defines the startup command
- `railway.toml` - Railway-specific configuration
- `nixpacks.toml` - Build configuration for Python + Node.js
- `start.py` - Startup script that manages both processes
- `requirements.txt` - Python dependencies
- `package.json` - Node.js dependencies

## Environment Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | `MTxxxxx...` |
| `DISCORD_CLIENT_ID` | Your Discord application ID | `1234567890` |
| `AUTHORIZED_USERS` | Comma-separated Discord user IDs | `123,456,789` |
| `MINECRAFT_HOST` | Minecraft server hostname | `east.donutsmp.net` |
| `MINECRAFT_PORT` | Minecraft server port | `25565` |
| `MINECRAFT_USERNAME` | Your Minecraft username | `YourUsername` |
| `MINECRAFT_PASSWORD` | Your Minecraft password | `YourPassword` |
| `MINECRAFT_TYPE` | Server type (Java/Bedrock) | `Java` |
| `MINECRAFT_VERSION` | Minecraft version | `1.21.5` |
| `AUTH_TYPE` | Authentication type | `microsoft` |
| `DONUTSMP_API_KEY` | DonutSMP API key | `abc123...` |
| `AFK_ACCOUNTS` | JSON object with AFK account credentials | `{"user1": "pass1", "user2": "pass2"}` |
| `AFK_HOST` | AFK accounts server host (optional) | `east.donutsmp.net` |
| `AFK_PORT` | AFK accounts server port (optional) | `25565` |
| `AFK_TYPE` | AFK accounts server type (optional) | `java` |
| `AFK_VERSION` | AFK accounts Minecraft version (optional) | `1.21.5` |
| `AFK_AUTH` | AFK accounts auth type (optional) | `microsoft` |

## Monitoring

- **Logs**: View logs in Railway dashboard under "Deployments" tab
- **Health Check**: Bot exposes health endpoint at `/health`
- **Status**: Use Discord `/status` command to check bot status

## Troubleshooting

### Build Fails
- Check that both `requirements.txt` and `package.json` are present
- Verify Python and Node.js versions in `nixpacks.toml`

### Bot Doesn't Start
- Check environment variables are set correctly
- Review logs for specific error messages
- Ensure Discord token is valid

### Minecraft Connection Issues
- Verify Minecraft server is accessible
- Check authentication credentials
- Ensure server allows connections from Railway's IP range

### Process Management
- The `start.py` script manages both Python and Node.js processes
- If one process crashes, it will attempt to restart automatically
- Check logs for process restart messages

## Support

If you encounter issues:
1. Check Railway logs for error messages
2. Verify all environment variables are set
3. Test locally first with `python start.py`
4. Check Discord bot permissions and server access
