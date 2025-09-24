const mineflayer = require('mineflayer');
const fs = require('fs');
const path = require('path');

class MinecraftClient {
    constructor() {
        this.bot = null;
        this.connected = false;
        this.authenticated = false;
        this.config = this.loadConfig();
        this.commandQueue = [];
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

    connect() {
        // Enable debug logging
        console.error = (...args) => console.log('[ERROR]', ...args);
        console.debug = (...args) => console.log('[DEBUG]', ...args);
        
        if (this.connected) {
            console.log('Already connected to Minecraft server');
            return;
        }

        console.log('🔌 Starting Microsoft authentication...');
        console.log(`Connecting to ${this.config.host}:${this.config.port} as ${this.config.username}`);
        
        try {
            const botConfig = {
                host: this.config.host,
                port: this.config.port,
                username: this.config.username,
                version: this.config.version,
                auth: this.config.auth,
                checkTimeoutInterval: 30000,
                hideErrors: false
            };
            
            // Add password if provided
            if (this.config.password) {
                botConfig.password = this.config.password;
            }
            
            this.bot = mineflayer.createBot(botConfig);

            this.bot.once('login', () => {
                console.log('✅ Successfully authenticated with Microsoft!');
                console.log(`Logged in as ${this.bot.username} (${this.bot.uuid})`);
                this.authenticated = true;
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
                if (err.stack) console.error(err.stack);
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