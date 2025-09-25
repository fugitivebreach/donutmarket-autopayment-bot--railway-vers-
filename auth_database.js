const mysql = require('mysql2/promise');

class AuthDatabase {
    constructor() {
        this.connection = null;
        
        // Debug environment variables
        console.log('🔍 MySQL Environment Variables:');
        console.log('MYSQLHOST:', process.env.MYSQLHOST);
        console.log('MYSQLUSER:', process.env.MYSQLUSER);
        console.log('MYSQLPORT:', process.env.MYSQLPORT);
        console.log('MYSQLDATABASE:', process.env.MYSQLDATABASE);
        console.log('MYSQL_ROOT_PASSWORD:', process.env.MYSQL_ROOT_PASSWORD);
        console.log('MYSQL_URL:', process.env.MYSQL_URL);
        console.log('RAILWAY_PRIVATE_DOMAIN:', process.env.RAILWAY_PRIVATE_DOMAIN);
        
        // Check if MYSQL_URL is provided (Railway format)
        if (process.env.MYSQL_URL) {
            console.log('🔗 Using MYSQL_URL for connection');
            // Parse the MySQL URL: mysql://user:password@host:port/database
            const url = new URL(process.env.MYSQL_URL);
            this.config = {
                host: url.hostname,
                port: parseInt(url.port) || 3306,
                user: url.username,
                password: url.password,
                database: url.pathname.slice(1), // Remove leading slash
                ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
                connectTimeout: 60000
            };
        } else {
            // Fallback to individual environment variables
            console.log('🔧 Using individual MySQL environment variables');
            this.config = {
                host: process.env.MYSQLHOST || process.env.RAILWAY_PRIVATE_DOMAIN || 'localhost',
                port: parseInt(process.env.MYSQLPORT || '3306'),
                user: process.env.MYSQLUSER || 'root',
                password: process.env.MYSQLPASSWORD || process.env.MYSQL_ROOT_PASSWORD || '',
                database: process.env.MYSQLDATABASE || process.env.MYSQL_DATABASE || 'railway',
                ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
                connectTimeout: 60000
            };
        }
        
        console.log('📋 MySQL Config:', {
            host: this.config.host,
            port: this.config.port,
            user: this.config.user,
            database: this.config.database,
            ssl: this.config.ssl
        });
    }

    async connect() {
        try {
            this.connection = await mysql.createConnection(this.config);
            console.log('✅ Connected to MySQL database');
            await this.initializeTables();
        } catch (error) {
            console.error('❌ Failed to connect to MySQL:', error.message);
            throw error;
        }
    }

    async initializeTables() {
        try {
            const createTableQuery = `
                CREATE TABLE IF NOT EXISTS minecraft_auth_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    minecraft_token TEXT,
                    expires_at BIGINT,
                    profile_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            `;
            await this.connection.execute(createTableQuery);
            
            // Add minecraft_token column if it doesn't exist (migration)
            try {
                await this.connection.execute(`
                    ALTER TABLE minecraft_auth_tokens 
                    ADD COLUMN minecraft_token TEXT AFTER refresh_token
                `);
                console.log('✅ Added minecraft_token column to existing table');
            } catch (error) {
                // Column already exists or other error - this is fine
                if (!error.message.includes('Duplicate column name')) {
                    console.log('ℹ️ minecraft_token column already exists or migration not needed');
                }
            }
            
            console.log('✅ Auth tokens table initialized');
        } catch (error) {
            console.error('❌ Failed to initialize tables:', error.message);
            throw error;
        }
    }

    async saveAuthTokens(username, tokenData) {
        try {
            const query = `
                INSERT INTO minecraft_auth_tokens 
                (username, access_token, refresh_token, minecraft_token, expires_at, profile_data)
                VALUES (?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                access_token = VALUES(access_token),
                refresh_token = VALUES(refresh_token),
                minecraft_token = VALUES(minecraft_token),
                expires_at = VALUES(expires_at),
                profile_data = VALUES(profile_data),
                updated_at = CURRENT_TIMESTAMP
            `;
            
            const values = [
                username,
                tokenData.access_token || null,
                tokenData.refresh_token || null,
                tokenData.minecraft_token || null,
                tokenData.expires_at || null,
                JSON.stringify(tokenData.profile || {})
            ];

            await this.connection.execute(query, values);
            console.log(`✅ Saved auth tokens for ${username}`);
        } catch (error) {
            console.error('❌ Failed to save auth tokens:', error.message);
            throw error;
        }
    }

    async getAuthTokens(username) {
        try {
            const query = 'SELECT * FROM minecraft_auth_tokens WHERE username = ?';
            const [rows] = await this.connection.execute(query, [username]);
            
            if (rows.length === 0) {
                return null;
            }

            const tokenData = rows[0];
            
            // Safe JSON parsing with fallback
            let profile = {};
            try {
                profile = JSON.parse(tokenData.profile_data || '{}');
            } catch (parseError) {
                console.error('⚠️ Failed to parse profile data, using default:', parseError.message);
                profile = { name: tokenData.username || 'unknown' };
            }
            
            return {
                access_token: tokenData.access_token,
                refresh_token: tokenData.refresh_token,
                minecraft_token: tokenData.minecraft_token,
                expires_at: tokenData.expires_at,
                profile: profile
            };
        } catch (error) {
            console.error('❌ Failed to get auth tokens:', error.message);
            return null;
        }
    }

    async deleteAuthTokens(username) {
        try {
            const query = 'DELETE FROM minecraft_auth_tokens WHERE username = ?';
            await this.connection.execute(query, [username]);
            console.log(`✅ Deleted auth tokens for ${username}`);
        } catch (error) {
            console.error('❌ Failed to delete auth tokens:', error.message);
        }
    }

    async isTokenValid(username) {
        try {
            const tokenData = await this.getAuthTokens(username);
            if (!tokenData) {
                console.log(`🔍 No tokens found for ${username}`);
                return false;
            }
            
            // Check if we have valid tokens (not the old placeholder tokens)
            const hasValidTokens = tokenData.access_token && 
                                 tokenData.access_token !== 'no_access_token' &&
                                 tokenData.access_token.length > 20;
            
            if (!hasValidTokens) {
                console.log(`🔄 Invalid tokens for ${username}, removing from database`);
                await this.deleteAuthTokens(username);
                return false;
            }
            
            // Check if token type indicates it's a permanent token
            const isPermanentToken = tokenData.access_token.startsWith('permanent_token_') ||
                                   tokenData.access_token.startsWith('msa_session_') ||
                                   tokenData.access_token.length > 100; // Real OAuth tokens are long
            
            if (isPermanentToken) {
                console.log(`✅ Valid permanent token found for ${username} (NEVER EXPIRES)`);
                return true;
            }
            
            // For non-permanent tokens, check expiry (legacy support)
            const now = Date.now();
            const expiresAt = new Date(tokenData.expires_at).getTime();
            
            if (now >= expiresAt) {
                console.log(`🔄 Token expired for ${username}, removing from database`);
                await this.deleteAuthTokens(username);
                return false;
            }
            
            console.log(`✅ Valid token found for ${username}, expires: ${new Date(expiresAt).toISOString()}`);
            return true;
        } catch (error) {
            console.error('❌ Failed to validate token:', error.message);
            return false;
        }
    }

    async close() {
        if (this.connection) {
            await this.connection.end();
            console.log('✅ MySQL connection closed');
        }
    }
}

module.exports = AuthDatabase;
