# Minecraft Payment Discord Bot (Python)

A Discord bot that connects to Minecraft servers (Java & Bedrock) to execute payment commands. This bot integrates with the DonutSMP API and allows you to send `/pay` commands in Minecraft through Discord slash commands with permission controls.

## Features

- 🤖 Discord bot with slash commands and embed replies
- ⛏️ Support for both Java and Bedrock Minecraft servers
- 💰 Execute `/pay {username} {amount}` commands with smart amount parsing (K, M, B, T suffixes)
- 🔐 Permission system based on Discord user IDs
- 🍩 DonutSMP API integration for balance checking
- 📊 Connection status monitoring
- 🛡️ Comprehensive error handling and logging
- 🎨 Beautiful embed responses with proper color coding

## Prerequisites

- Python 3.8 or higher
- A Discord bot token
- A Minecraft account (Java Edition or Bedrock)
- DonutSMP API key (get with `/api` command in-game)
- Access to a Minecraft server

## Installation

### Local Development

1. **Clone or download this project**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

4. **Set up environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in your configuration details

### Railway Deployment

This bot is configured to deploy on Railway with both Python and Node.js support.

1. **Fork or clone this repository**

2. **Connect to Railway:**
   - Go to [Railway](https://railway.app)
   - Create a new project from your GitHub repository
   - Railway will automatically detect the configuration

3. **Set Environment Variables in Railway:**
   - Go to your Railway project dashboard
   - Navigate to Variables tab
   - Add all the required environment variables from `.env.example`

4. **Deploy:**
   - Railway will automatically build and deploy your bot
   - The bot will start with both Python Discord bot and Node.js Minecraft client

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CLIENT_ID=your_discord_client_id_here

# Discord Permissions (comma-separated user IDs)
AUTHORIZED_USERS=123456789012345678,987654321098765432

# Minecraft Server Configuration
MINECRAFT_HOST=donutsmp.net
MINECRAFT_PORT=19132
MINECRAFT_USERNAME=your_minecraft_username
MINECRAFT_PASSWORD=your_minecraft_password

# Minecraft Type: Java or Bedrock
MINECRAFT_TYPE=Java

# Optional: Minecraft version (defaults to latest)
MINECRAFT_VERSION=1.21.70

# Optional: Authentication type (microsoft, mojang, or offline)
AUTH_TYPE=microsoft

# DonutSMP API Configuration
DONUTSMP_API_KEY=your_donutsmp_api_key_here

# AFK Accounts Configuration (JSON format)
AFK_ACCOUNTS={"username1": "password1", "username2": "password2"}

# AFK Account Server Configuration (optional, defaults to main account settings)
AFK_HOST=east.donutsmp.net
AFK_PORT=25565
AFK_TYPE=java
AFK_VERSION=1.21.5
AFK_AUTH=microsoft
```

### Discord Bot Setup

1. **Create a Discord Application:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Go to the "Bot" section and create a bot
   - Copy the bot token and add it to your `.env` file as `DISCORD_TOKEN`
   - Copy the Application ID and add it to your `.env` file as `DISCORD_CLIENT_ID`

2. **Bot Permissions:**
   - In the Discord Developer Portal, go to OAuth2 > URL Generator
   - Select "bot" and "applications.commands" scopes
   - Select the following bot permissions:
     - Send Messages
     - Use Slash Commands
   - Use the generated URL to invite the bot to your server

### Permission Setup

1. **Get Discord User IDs:**
   - Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
   - Right-click on users and select "Copy User ID"
   - Add these IDs to `AUTHORIZED_USERS` in your `.env` file (comma-separated)

### DonutSMP API Setup

1. **Get API Key:**
   - Join the DonutSMP server
   - Run `/api` command in-game to generate your API key
   - Copy the key and add it to your `.env` file as `DONUTSMP_API_KEY`

### Minecraft Account Setup

- **Microsoft Account (Recommended):** Use your Microsoft account credentials
- **Mojang Account:** Use your Mojang account credentials (legacy)
- **Offline Mode:** Set `AUTH_TYPE=offline` and only provide a username
- **Server Type:** Set `MINECRAFT_TYPE` to either "Java" or "Bedrock"

## Usage

### Local Development

1. **Start the bot:**
   ```bash
   python bot.py
   ```

### Railway Deployment

Once deployed on Railway, the bot will automatically start and be available 24/7.

**Discord Commands:**

- `/connect` - Connect the bot to the Minecraft server
- `/disconnect` - Disconnect the bot from the Minecraft server
- `/pay <username> <amount>` - Send money to a player (supports K, M, B, T suffixes)
- `/status` - Check the bot's connection status
- `/afk connect` - Connect all configured AFK accounts
- `/afk on` - Connect all AFK accounts and run /warp afk
- `/afk disconnect` - Disconnect all AFK accounts
- `/afk status` - Check status of all AFK accounts

## Example Workflow

1. Start the bot: `python bot.py`
2. In Discord, use `/connect` to connect to the Minecraft server
3. Use `/pay PlayerName 100M` to send 100 million currency to PlayerName
4. Use `/status` to check if the bot is still connected
5. Use `/disconnect` when done

## Amount Formatting

The bot supports various amount formats:
- `100` - Regular numbers
- `1K` - 1,000
- `5M` - 5,000,000
- `2B` - 2,000,000,000
- `1T` - 1,000,000,000,000

## Railway-Specific Features

This bot is optimized for Railway deployment with:

- **Automatic Process Management:** Both Python Discord bot and Node.js Minecraft client run simultaneously
- **Environment Variable Support:** All configuration through Railway environment variables
- **Logging:** Structured logging that works with Railway's log viewer
- **Auto-restart:** Processes automatically restart if they crash
- **Multi-language Support:** Python and Node.js dependencies managed automatically

### Railway Environment Variables

Set these in your Railway project dashboard:

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_CLIENT_ID=your_discord_client_id
AUTHORIZED_USERS=comma_separated_user_ids
MINECRAFT_HOST=east.donutsmp.net
MINECRAFT_PORT=25565
MINECRAFT_USERNAME=your_username
MINECRAFT_PASSWORD=your_password
MINECRAFT_TYPE=Java
MINECRAFT_VERSION=1.21.5
AUTH_TYPE=microsoft
DONUTSMP_API_KEY=your_api_key
AFK_ACCOUNTS={"SappedNap": "Arrow147527", "N4yzen": "Arrow147527", "DorDunutt": "Arrow147527", "jiujiellunh": "Arrow147527", "DrCodes": "Arrow147527", "El_Gavilan": "Arrow147527", "aug14": "Arrow147527"}
AFK_HOST=east.donutsmp.net
AFK_PORT=25565
AFK_TYPE=java
AFK_VERSION=1.21.5
AFK_AUTH=microsoft
```

### Migrating from afk_accounts.json

If you have an existing `afk_accounts.json` file, you can use the migration script:

```bash
python migrate_afk_config.py
```

This will output the environment variables you need to set. The bot will automatically use environment variables if available, and fall back to the JSON file if not.

## Troubleshooting

### Common Issues

1. **"Invalid token" error:**
   - Make sure your Discord bot token is correct in the `.env` file
   - Ensure there are no extra spaces or quotes around the token

2. **"Connection failed" to Minecraft:**
   - Verify the server IP and port are correct
   - Check if the server is online and accessible
   - Ensure your Minecraft account credentials are valid
   - Try different authentication types (microsoft, mojang, offline)

3. **"Command not found" in Discord:**
   - Make sure the bot has been invited with the correct permissions
   - Wait a few minutes for slash commands to register globally
   - Try kicking and re-inviting the bot

4. **"Insufficient Permissions" message:**
   - Make sure your Discord User ID is in the `AUTHORIZED_USERS` list
   - Check that the User ID is correct (enable Developer Mode in Discord)
   - Ensure there are no extra spaces in the `.env` file

5. **DonutSMP API errors:**
   - Verify your API key is correct (generate new one with `/api` in-game)
   - Check that you have the correct permissions on the server
   - Ensure the target username exists and is spelled correctly

6. **Payment command not working:**
   - Ensure the Minecraft server supports the `/pay` command
   - Check if your bot account has permission to use the command
   - Verify you have sufficient balance for the payment

### Railway-Specific Issues

1. **Bot not starting on Railway:**
   - Check the Railway logs for error messages
   - Verify all environment variables are set correctly
   - Ensure both Python and Node.js dependencies are installed

2. **Process crashes on Railway:**
   - Check Railway logs for specific error messages
   - Verify Minecraft server is accessible from Railway's network
   - Check if authentication credentials are valid

3. **Environment variables not working:**
   - Make sure variables are set in Railway dashboard, not just .env file
   - Restart the deployment after adding new variables
   - Check variable names match exactly (case-sensitive)

4. **Node.js process not starting:**
   - Check if npm install completed successfully in build logs
   - Verify Node.js version compatibility (requires Node 18+)
   - Check for any missing Node.js dependencies

## Embed Response Colors

The bot uses specific colors for different response types:
- 🔵 **Success (Dark Blue):** Successful operations
- 🟡 **Warning (Dark Gold):** Errors and insufficient permissions
- 🔵 **Info (Blue):** Status information

## Security Notes

- Never share your `.env` file or commit it to version control
- Use environment variables for all sensitive information
- Consider using a dedicated Minecraft account for the bot
- Regularly rotate your Discord bot token and API keys if compromised
- Only give bot permissions to trusted Discord users

## Customization

You can modify the bot to:
- Add more Minecraft commands
- Implement command cooldowns
- Add role-based permissions instead of user ID permissions
- Store transaction logs in a database
- Add a web dashboard
- Support multiple Minecraft servers

## Dependencies

- `discord.py` - Discord API wrapper for Python
- `requests` - HTTP library for API calls
- `python-dotenv` - Environment variable loader
- `aiohttp` - Async HTTP client

## License

MIT License - feel free to modify and distribute as needed.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your configuration in the `.env` file
3. Check the console logs for error messages
4. Ensure all dependencies are properly installed
