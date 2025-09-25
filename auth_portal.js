const express = require('express');
const axios = require('axios');
const crypto = require('crypto');

class AuthPortal {
    constructor(authDB) {
        this.authDB = authDB;
        this.app = express();
        this.server = null;
        this.port = process.env.PORT ? parseInt(process.env.PORT) + 1 : 3001;
        
        // Get Railway public URL or fallback to localhost
        const baseUrl = process.env.RAILWAY_PUBLIC_DOMAIN 
            ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`
            : `http://localhost:${this.port}`;
        
        // Microsoft OAuth2 configuration
        this.clientId = '00000000402b5328'; // Minecraft client ID
        this.redirectUri = `${baseUrl}/auth/callback`;
        this.scope = 'XboxLive.signin offline_access';
        this.baseUrl = baseUrl;
        
        this.setupRoutes();
    }
    
    setupRoutes() {
        this.app.use(express.json());
        this.app.use(express.static('public'));
        
        // Main auth page
        this.app.get('/', (req, res) => {
            res.send(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>DonutMarket Bot Authentication</title>
                    <style>
                        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                        .btn { background: #0078d4; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }
                        .success { color: green; font-weight: bold; }
                        .error { color: red; font-weight: bold; }
                        .token-info { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }
                    </style>
                </head>
                <body>
                    <h1>🎮 DonutMarket Bot Authentication</h1>
                    <p>Click the button below to authenticate with Microsoft and save your tokens permanently:</p>
                    <a href="/auth/start" class="btn">🔐 Authenticate with Microsoft</a>
                    
                    <h3>📋 Instructions:</h3>
                    <ol>
                        <li>Click "Authenticate with Microsoft"</li>
                        <li>Sign in with your Minecraft account</li>
                        <li>Your tokens will be saved to the database</li>
                        <li>Future deployments won't need authentication!</li>
                    </ol>
                </body>
                </html>
            `);
        });
        
        // Start OAuth flow
        this.app.get('/auth/start', (req, res) => {
            const state = crypto.randomBytes(16).toString('hex');
            const authUrl = `https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?` +
                `client_id=${this.clientId}&` +
                `response_type=code&` +
                `redirect_uri=${encodeURIComponent(this.redirectUri)}&` +
                `scope=${encodeURIComponent(this.scope)}&` +
                `state=${state}`;
            
            console.log('🔐 Starting Microsoft OAuth flow...');
            res.redirect(authUrl);
        });
        
        // Handle OAuth callback
        this.app.get('/auth/callback', async (req, res) => {
            const { code, error } = req.query;
            
            if (error) {
                console.error('❌ OAuth error:', error);
                return res.send(`<h1>❌ Authentication Failed</h1><p>Error: ${error}</p>`);
            }
            
            if (!code) {
                return res.send(`<h1>❌ Authentication Failed</h1><p>No authorization code received</p>`);
            }
            
            try {
                console.log('🔄 Exchanging code for tokens...');
                
                // Exchange code for tokens
                const tokenResponse = await axios.post('https://login.microsoftonline.com/consumers/oauth2/v2.0/token', 
                    new URLSearchParams({
                        client_id: this.clientId,
                        code: code,
                        redirect_uri: this.redirectUri,
                        grant_type: 'authorization_code'
                    }), {
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                    }
                );
                
                const tokens = tokenResponse.data;
                console.log('✅ Got Microsoft tokens!');
                
                // Get Xbox Live token
                const xblResponse = await axios.post('https://user.auth.xboxlive.com/user/authenticate', {
                    Properties: {
                        AuthMethod: 'RPS',
                        SiteName: 'user.auth.xboxlive.com',
                        RpsTicket: `d=${tokens.access_token}`
                    },
                    RelyingParty: 'http://auth.xboxlive.com',
                    TokenType: 'JWT'
                }, {
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const xblToken = xblResponse.data.Token;
                const userHash = xblResponse.data.DisplayClaims.xui[0].uhs;
                console.log('✅ Got Xbox Live token!');
                
                // Get XSTS token
                const xstsResponse = await axios.post('https://xsts.auth.xboxlive.com/xsts/authorize', {
                    Properties: {
                        SandboxId: 'RETAIL',
                        UserTokens: [xblToken]
                    },
                    RelyingParty: 'rp://api.minecraftservices.com/',
                    TokenType: 'JWT'
                }, {
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const xstsToken = xstsResponse.data.Token;
                console.log('✅ Got XSTS token!');
                
                // Get Minecraft token
                const mcResponse = await axios.post('https://api.minecraftservices.com/authentication/login_with_xbox', {
                    identityToken: `XBL3.0 x=${userHash};${xstsToken}`
                }, {
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const mcToken = mcResponse.data.access_token;
                console.log('✅ Got Minecraft token!');
                
                // Get Minecraft profile
                const profileResponse = await axios.get('https://api.minecraftservices.com/minecraft/profile', {
                    headers: { 'Authorization': `Bearer ${mcToken}` }
                });
                
                const profile = profileResponse.data;
                console.log('✅ Got Minecraft profile:', profile.name);
                
                // Save to database
                const tokenData = {
                    access_token: tokens.access_token,
                    refresh_token: tokens.refresh_token,
                    minecraft_token: mcToken,
                    expires_at: Date.now() + (365 * 24 * 60 * 60 * 1000), // Never expire (1 year)
                    profile: {
                        name: profile.name,
                        id: profile.id
                    }
                };
                
                await this.authDB.saveAuthTokens(profile.name, tokenData);
                console.log('💾 Saved real Microsoft tokens to database!');
                
                res.send(`
                    <h1>✅ Authentication Successful!</h1>
                    <div class="token-info">
                        <h3>🎮 Profile Information:</h3>
                        <p><strong>Username:</strong> ${profile.name}</p>
                        <p><strong>UUID:</strong> ${profile.id}</p>
                        <p><strong>Access Token Length:</strong> ${tokens.access_token.length} chars</p>
                        <p><strong>Refresh Token Length:</strong> ${tokens.refresh_token.length} chars</p>
                        <p><strong>Minecraft Token Length:</strong> ${mcToken.length} chars</p>
                        <p><strong>Expires:</strong> Never (1 year from now)</p>
                    </div>
                    <div class="success">
                        <h3>🚀 Your tokens have been saved!</h3>
                        <p>Future Railway deployments will use these tokens automatically.</p>
                        <p>You can close this window and redeploy your bot.</p>
                    </div>
                `);
                
            } catch (error) {
                console.error('❌ Token exchange failed:', error.message);
                res.send(`<h1>❌ Authentication Failed</h1><p>Error: ${error.message}</p>`);
            }
        });
        
        // Health check
        this.app.get('/health', (req, res) => {
            res.json({ status: 'ok', message: 'Auth portal is running' });
        });
    }
    
    async start() {
        return new Promise((resolve, reject) => {
            this.server = this.app.listen(this.port, (err) => {
                if (err) {
                    console.error('❌ Failed to start auth portal:', err);
                    reject(err);
                } else {
                    console.log(`🌐 Auth portal running at ${this.baseUrl}`);
                    console.log(`🔐 Visit ${this.baseUrl} to authenticate`);
                    resolve();
                }
            });
        });
    }
    
    async stop() {
        if (this.server) {
            return new Promise((resolve) => {
                this.server.close(() => {
                    console.log('🔒 Auth portal stopped');
                    resolve();
                });
            });
        }
    }
}

module.exports = AuthPortal;
