const mysql = require('mysql2/promise');

class AuthDatabase {
    constructor() {
        this.connection = null;
        this.config = {
            host: process.env.MYSQLHOST || process.env.MYSQL_HOST || 'localhost',
            port: parseInt(process.env.MYSQLPORT || process.env.MYSQL_PORT || '3306'),
            user: process.env.MYSQLUSER || process.env.MYSQL_USER || 'root',
            password: process.env.MYSQLPASSWORD || process.env.MYSQL_ROOT_PASSWORD || '',
            database: process.env.MYSQLDATABASE || process.env.MYSQL_DATABASE || 'railway',
            ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
        };
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
                    expires_at BIGINT,
                    profile_data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            `;
            await this.connection.execute(createTableQuery);
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
                (username, access_token, refresh_token, expires_at, profile_data)
                VALUES (?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                access_token = VALUES(access_token),
                refresh_token = VALUES(refresh_token),
                expires_at = VALUES(expires_at),
                profile_data = VALUES(profile_data),
                updated_at = CURRENT_TIMESTAMP
            `;
            
            const values = [
                username,
                tokenData.access_token || null,
                tokenData.refresh_token || null,
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
            return {
                access_token: tokenData.access_token,
                refresh_token: tokenData.refresh_token,
                expires_at: tokenData.expires_at,
                profile: JSON.parse(tokenData.profile_data || '{}')
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
            if (!tokenData || !tokenData.expires_at) {
                return false;
            }

            const now = Date.now();
            const expiresAt = parseInt(tokenData.expires_at);
            
            // Consider token valid if it expires more than 5 minutes from now
            return expiresAt > (now + 5 * 60 * 1000);
        } catch (error) {
            console.error('❌ Failed to check token validity:', error.message);
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
