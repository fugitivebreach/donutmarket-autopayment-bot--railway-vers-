const mineflayer = require('mineflayer');
const fs = require('fs');
const path = require('path');
const AuthDatabase = require('./auth_database');

class MinecraftClient {
    constructor() {
        this.bot = null;
        this.connected = false;
        this.authenticated = false;
        this.config = this.loadConfig();
        this.commandQueue = [];
        this.authDB = new AuthDatabase();
        this.setupCommandListener();
    }

    loadConfig() {
        // Load from environment variables or use defaults
        return {
            host: process.env.MINECRAFT_HOST || 'east.donutsmp.net',
            port: parseInt(process.env.MINECRAFT_PORT || '25565'),
            username: process.env.MINECRAFT_USERNAME || 'mnidia0811@gmail.com',
            password: process.env.MINECRAFT_PASSWORD,
            version: process.env.MINECRAFT_VERSION || '1.21.5',
            auth: process.env.AUTH_TYPE || 'microsoft'
        };
    }

    setupCommandListener() {
        // Check for both general command file and account-specific command file
        const generalCommandFile = path.join(__dirname, 'minecraft_command.txt');
        const accountCommandFile = path.join(__dirname, `minecraft_command_${this.config.username}.txt`);
        
        // Check for commands every 500ms
        setInterval(() => {
            if (!this.connected) return;
            
            // Check general command file first
            if (fs.existsSync(generalCommandFile)) {
                try {
                    const command = fs.readFileSync(generalCommandFile, 'utf8').trim();
                    if (command) {
                        console.log(`[${this.config.username}] Executing general command: ${command}`);
                        this.bot.chat(command);
                        fs.unlinkSync(generalCommandFile);
                    }
                } catch (error) {
                    console.error('Error processing general command:', error);
                }
            }
            
            // Check account-specific command file
            if (fs.existsSync(accountCommandFile)) {
                try {
                    const command = fs.readFileSync(accountCommandFile, 'utf8').trim();
                    if (command) {
                        console.log(`[${this.config.username}] Executing account command: ${command}`);
                        this.bot.chat(command);
                        fs.unlinkSync(accountCommandFile);
                    }
                } catch (error) {
                    console.error('Error processing account command:', error);
                }
            }
        }, 500);
    }

    async connect() {
        // Enable debug logging
        console.error = (...args) => console.log('[ERROR]', ...args);
        console.debug = (...args) => console.log('[DEBUG]', ...args);
        
        if (this.connected) {
            console.log('Already connected to Minecraft server');
            return;
        }

        console.log('🔌 Starting Minecraft authentication...');
        console.log(`Connecting to ${this.config.host}:${this.config.port} as ${this.config.username}`);
        
        // Debug: Show all environment variables that start with MYSQL
        console.log('🔍 Available MySQL environment variables:');
        Object.keys(process.env).filter(key => key.includes('MYSQL')).forEach(key => {
            console.log(`${key}:`, process.env[key] ? '[SET]' : '[NOT SET]');
        });
        
        try {
            // Try to initialize database connection
            let dbConnected = false;
            try {
                await this.authDB.connect();
                dbConnected = true;
                console.log('✅ MySQL database connected successfully');
            } catch (dbError) {
                console.error('⚠️ MySQL connection failed, continuing without database caching:', dbError.message);
                console.log('🔄 Bot will work normally but authentication won\'t be cached');
                dbConnected = false;
            }
            
            // Store tokens when authentication completes (declare at function scope)
            let authTokens = null;
            
            // Hook into prismarine-auth to capture real tokens
            const { Authflow } = require('prismarine-auth');
            const originalGetMinecraftJavaToken = Authflow.prototype.getMinecraftJavaToken;
            
            Authflow.prototype.getMinecraftJavaToken = async function(options) {
                console.log('🔍 Intercepting Microsoft authentication flow...');
                const result = await originalGetMinecraftJavaToken.call(this, options);
                
                // Debug: Log the entire auth flow object structure
                console.log('🔍 Auth flow object keys:', Object.keys(this));
                console.log('🔍 MSA object:', this.msa ? Object.keys(this.msa) : 'null');
                console.log('🔍 Result object:', result ? Object.keys(result) : 'null');
                
                // Try multiple ways to access the tokens
                let msaToken = null;
                let refreshToken = null;
                
                // Method 1: Direct MSA access
                if (this.msa && this.msa.access_token) {
                    msaToken = this.msa.access_token;
                    refreshToken = this.msa.refresh_token;
                    console.log('✅ Found tokens via this.msa');
                }
                
                // Method 2: Check if tokens are in different location
                if (!msaToken && this.msaToken) {
                    msaToken = this.msaToken.access_token;
                    refreshToken = this.msaToken.refresh_token;
                    console.log('✅ Found tokens via this.msaToken');
                }
                
                // Method 3: Check if tokens are in the result
                if (!msaToken && result.msaToken) {
                    msaToken = result.msaToken.access_token;
                    refreshToken = result.msaToken.refresh_token;
                    console.log('✅ Found tokens via result.msaToken');
                }
                
                if (msaToken) {
                    console.log('🔥 REAL Microsoft tokens captured!');
                    authTokens = {
                        access_token: msaToken,
                        refresh_token: refreshToken,
                        minecraft_token: result.access_token,
                        expires_at: Date.now() + (365 * 24 * 60 * 60 * 1000), // 1 year
                        profile: {
                            name: result.username || result.name,
                            id: result.uuid || result.id
                        }
                    };
                    
                    console.log('🎯 Real token data captured:', {
                        msaTokenLength: msaToken.length,
                        refreshTokenLength: refreshToken?.length || 0,
                        mcTokenLength: result.access_token.length,
                        username: result.username || result.name,
                        uuid: result.uuid || result.id
                    });
                } else {
                    console.log('⚠️ MSA tokens not found in any location');
                    console.log('🔍 Available properties:', {
                        thisKeys: Object.keys(this),
                        resultKeys: Object.keys(result)
                    });
                }
                
                return result;
            };
            
            const botConfig = {
                host: this.config.host,
                port: this.config.port,
                username: this.config.username,
                version: this.config.version,
                auth: this.config.auth,
                checkTimeoutInterval: 30000,
                hideErrors: false
            };
            
            // Handle Microsoft authentication with optional MySQL token storage
            if (this.config.auth === 'microsoft') {
                // For Microsoft auth, we must NOT include a password field
                delete botConfig.password;
                
                // Check if we have valid cached tokens (only if database is connected)
                if (dbConnected) {
                    try {
                        const isTokenValid = await this.authDB.isTokenValid(this.config.username);
                        if (isTokenValid) {
                            console.log('🔐 Using cached Microsoft authentication tokens from database');
                            const cachedTokens = await this.authDB.getAuthTokens(this.config.username);
                            if (cachedTokens) {
                                botConfig.session = {
                                    accessToken: cachedTokens.access_token,
                                    clientToken: cachedTokens.refresh_token,
                                    selectedProfile: cachedTokens.profile
                                };
                            }
                        }
                    } catch (tokenError) {
                        console.error('⚠️ Failed to retrieve cached tokens:', tokenError.message);
                    }
                }
                
                // Check if we have valid cached tokens first
                const isTokenValid = await this.authDB.isTokenValid(this.config.username);
                if (isTokenValid) {
                    console.log('✅ Using cached authentication tokens from database');
                    const cachedTokens = await this.authDB.getAuthTokens(this.config.username);
                    if (cachedTokens && cachedTokens.minecraft_token) {
                        // Use the cached Minecraft token directly
                        botConfig.session = {
                            accessToken: cachedTokens.minecraft_token,
                            clientToken: cachedTokens.refresh_token,
                            selectedProfile: cachedTokens.profile
                        };
                        console.log('🔐 Using cached Minecraft token for direct login');
                    }
                }
                
                botConfig.onMsaCode = (data) => {
                    console.log('🔐 Microsoft Authentication Required');
                    console.log('📱 Please visit the following URL to authenticate:');
                    console.log(`🌐 ${data.verification_uri}`);
                    console.log('🔢 Enter this device code when prompted:');
                    console.log(`📋 ${data.user_code}`);
                    console.log('⏰ You have 15 minutes to complete authentication');
                    console.log('🔄 Waiting for authentication...');
                    console.log('💡 Note: Tokens will be saved to database (never expire)');
                };
                
                const storageType = dbConnected ? 'MySQL token storage' : 'no caching (database unavailable)';
                console.log(`🔐 Using Microsoft authentication (OAuth2 flow with ${storageType})`);
            } else {
                // For non-Microsoft auth, add password if provided
                if (this.config.password) {
                    botConfig.password = this.config.password;
                }
                console.log(`Using auth mode: ${botConfig.auth}`);
            }
            
            this.bot = mineflayer.createBot(botConfig);

            this.bot.once('login', async () => {
                console.log('✅ Successfully authenticated!');
                console.log(`Logged in as ${this.bot.username} (${this.bot.uuid})`);
                this.authenticated = true;
                
                // Save REAL authentication tokens to database for Microsoft auth (if database is connected)
                if (this.config.auth === 'microsoft' && dbConnected) {
                    try {
                        console.log('🔍 Attempting to save REAL auth tokens...');
                        console.log('Real tokens available:', !!authTokens);
                        console.log('Bot username:', this.bot.username);
                        console.log('Bot UUID:', this.bot.uuid);
                        
                        if (authTokens) {
                            // Use the REAL captured Microsoft tokens
                            const tokenData = {
                                access_token: authTokens.access_token,
                                refresh_token: authTokens.refresh_token,
                                minecraft_token: authTokens.minecraft_token,
                                expires_at: authTokens.expires_at,
                                profile: authTokens.profile
                            };
                            
                            console.log('🔥 REAL Microsoft token data prepared:', {
                                username: this.config.username,
                                msaTokenLength: tokenData.access_token.length,
                                refreshTokenLength: tokenData.refresh_token?.length || 0,
                                mcTokenLength: tokenData.minecraft_token.length,
                                profileName: tokenData.profile.name,
                                profileId: tokenData.profile.id,
                                realTokens: true
                            });
                            
                            await this.authDB.saveAuthTokens(this.config.username, tokenData);
                            console.log('💾 Saved REAL Microsoft authentication tokens to database!');
                        } else {
                            console.log('⚠️ No real tokens captured - authentication hook may have failed');
                        }
                    } catch (error) {
                        console.error('❌ Failed to save real auth tokens:', error.message);
                        console.error('Full error:', error);
                    }
                } else {
                    console.log('🔍 Token save skipped - Auth:', this.config.auth, 'DB Connected:', dbConnected);
                }
            });

            this.bot.once('spawn', async () => {
                console.log('🌍 Spawned in the world');
                this.connected = true;
                this.updateStatusFile(true, 'Connected to server');
                
                // Wait a bit before sending the welcome message
                console.log('Waiting before sending welcome message...');
                await new Promise(resolve => setTimeout(resolve, 5000));
                
                try {
                    // Send welcome message to DrGlaze
                    console.log('Sending welcome message to DrGlaze...');
                    this.bot.chat('/w DrGlaze hello');
                    console.log('👋 Successfully sent welcome message to DrGlaze');
                    
                    // Send a test message to chat
                    setTimeout(() => {
                        this.bot.chat('Bot is now online!');
                        console.log('✅ Sent test chat message');
                    }, 2000);
                } catch (error) {
                    console.error('❌ Failed to send welcome message:', error);
                }
            });

            this.bot.on('message', (message) => {
                const msg = message.toString().trim();
                
                // Filter messages - only show system/server messages and own commands
                const isSystemMessage = (
                    msg.includes('You teleported to') ||
                    msg.includes('teleported to') ||
                    msg.includes('joined the game') ||
                    msg.includes('left the game') ||
                    msg.includes('sent you a tpa request') ||
                    msg.includes('[CLICK]') ||
                    msg.includes('This teleport request') ||
                    msg.includes('Server') ||
                    msg.includes('kicked') ||
                    msg.includes('banned') ||
                    msg.includes('Kicked') ||
                    msg.includes('Banned') ||
                    msg.includes('YOU ->') ||  // Own whispers
                    msg.includes(`${this.config.username}:`) ||  // Own chat messages
                    msg.includes(`${this.config.username} `) ||  // Messages about this bot
                    msg.startsWith('[') ||  // System messages usually start with brackets
                    !msg.includes(':')  // System messages usually don't have colons (no username:)
                );
                
                if (isSystemMessage) {
                    console.log(`💬 [Chat] ${msg}`);
                }
            });

            this.bot.on('error', (err) => {
                console.error('❌ Minecraft client error:', err.message);
                console.error('[ERROR]', err);
                
                // Check for specific offline mode rejection
                if (err.message.includes('online-mode') || err.message.includes('premium') || err.message.includes('authentication')) {
                    console.error('🚫 Server requires premium authentication - offline mode not allowed');
                    console.error('💡 Try switching back to Microsoft authentication or use a different account');
                }
                
                this.connected = false;
                this.authenticated = false;
                this.updateStatusFile(false, `Error: ${err.message}`);
            });

            this.bot.on('end', (reason) => {
                console.log(`🔌 Disconnected: ${reason}`);
                this.connected = false;
                this.authenticated = false;
                this.updateStatusFile(false, `Disconnected: ${reason}`);
                
                // Attempt to reconnect after 10 seconds
                console.log('Attempting to reconnect in 10 seconds...');
                setTimeout(() => this.connect(), 10000);
            });

            this.bot.on('kicked', (reason) => {
                console.log(`👢 Kicked: ${reason}`);
                this.updateStatusFile(false, `Kicked: ${reason}`);
            });
            
            // Log all events for debugging
            this.bot.on('raw', (packet) => {
                // Uncomment for detailed packet logging
                // console.log('[PACKET]', packet.name);
            });
            
        } catch (error) {
            console.error('❌ Failed to create Minecraft client:', error);
            this.updateStatusFile(false, `Failed to create client: ${error.message}`);
            
            // Attempt to reconnect after 10 seconds on error
            console.log('Attempting to reconnect in 10 seconds...');
            setTimeout(() => this.connect(), 10000);
        }
    }

    disconnect() {
        if (!this.connected) {
            console.log('Not connected to Minecraft server');
            return;
        }

        try {
            this.bot.quit('Disconnecting...');
            console.log('Disconnected from Minecraft server');
            this.updateStatusFile(false, 'Disconnected by user');
        } catch (error) {
            console.error('Error disconnecting:', error);
        } finally {
            this.connected = false;
            this.authenticated = false;
        }
    }

    updateStatusFile(connected, message) {
        const status = {
            connected,
            message,
            username: this.config.username,
            timestamp: new Date().toISOString()
        };

        try {
            // Only write to the main minecraft_status.json file
            fs.writeFileSync(
                path.join(__dirname, 'minecraft_status.json'),
                JSON.stringify(status, null, 2)
            );
        } catch (error) {
            console.error('Error writing status file:', error);
        }
    }
}

// Handle command line arguments
const client = new MinecraftClient();
const args = process.argv.slice(2);

if (args[0] === 'connect') {
    client.connect();
} else if (args[0] === 'disconnect') {
    client.disconnect();
}

// Export for potential future use
module.exports = { MinecraftClient };