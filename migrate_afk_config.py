#!/usr/bin/env python3
"""
Migration script to convert afk_accounts.json to environment variables format.
This script reads the existing afk_accounts.json file and outputs the environment variables
that should be set in Railway or your .env file.
"""

import json
import os

def migrate_afk_config():
    """Convert afk_accounts.json to environment variables format"""
    
    afk_config_path = 'afk_accounts.json'
    
    if not os.path.exists(afk_config_path):
        print("❌ afk_accounts.json not found in current directory")
        return
    
    try:
        with open(afk_config_path, 'r') as f:
            config = json.load(f)
        
        print("🔄 Converting afk_accounts.json to environment variables format...\n")
        
        # Extract AFK accounts
        afk_accounts = config.get('afk_accounts', [])
        if not afk_accounts:
            print("❌ No AFK accounts found in configuration")
            return
        
        # Build the AFK_ACCOUNTS JSON string
        afk_accounts_dict = {}
        for account in afk_accounts:
            username = account.get('minecraft_username')
            password = account.get('minecraft_password')
            if username and password:
                afk_accounts_dict[username] = password
        
        if not afk_accounts_dict:
            print("❌ No valid AFK accounts found")
            return
        
        # Get server configuration from first account (assuming all are the same)
        first_account = afk_accounts[0]
        
        print("📋 Add these environment variables to Railway or your .env file:\n")
        print("# AFK Accounts Configuration")
        print(f"AFK_ACCOUNTS={json.dumps(afk_accounts_dict)}")
        print(f"AFK_HOST={first_account.get('minecraft_host', 'east.donutsmp.net')}")
        print(f"AFK_PORT={first_account.get('minecraft_port', 25565)}")
        print(f"AFK_TYPE={first_account.get('minecraft_type', 'java')}")
        print(f"AFK_VERSION={first_account.get('minecraft_version', '1.21.5')}")
        print(f"AFK_AUTH={first_account.get('minecraft_authtype', 'microsoft')}")
        
        print(f"\n✅ Found {len(afk_accounts_dict)} AFK accounts:")
        for username in afk_accounts_dict.keys():
            print(f"   - {username}")
        
        print("\n📝 Instructions:")
        print("1. Copy the environment variables above")
        print("2. Add them to your Railway project dashboard (Variables tab)")
        print("3. Or add them to your .env file for local development")
        print("4. The bot will automatically use environment variables instead of JSON")
        print("5. You can safely delete afk_accounts.json after migration")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing afk_accounts.json: {e}")
    except Exception as e:
        print(f"❌ Error reading afk_accounts.json: {e}")

if __name__ == "__main__":
    migrate_afk_config()
