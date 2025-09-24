import os
import re
import asyncio
import logging
import requests
import subprocess
import time
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from aiohttp import web
import threading

# Load environment variables
load_dotenv()

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Ensure logs go to stdout for Railway
    ]
)
logger = logging.getLogger(__name__)

def parse_amount(amount_str: str) -> Optional[float]:
    """
    Parse a string amount with K, M, B, T suffixes into a float.
    
    Args:
        amount_str: The amount string to parse (e.g., '10K', '5M', '1.5B')
        
    Returns:
        float: The parsed amount, or None if invalid
    """
    if not amount_str:
        return None
        
    # Remove any commas and spaces
    amount_str = amount_str.strip().replace(',', '')
    
    # Check if it's a plain number
    if amount_str.replace('.', '').isdigit():
        return float(amount_str)
    
    # Check for K, M, B, T suffixes
    suffix_multipliers = {
        'K': 1_000,
        'M': 1_000_000,
        'B': 1_000_000_000,
        'T': 1_000_000_000_000
    }
    
    # Check if the last character is a valid suffix
    suffix = amount_str[-1].upper()
    if suffix in suffix_multipliers:
        try:
            number = float(amount_str[:-1])
            return number * suffix_multipliers[suffix]
        except (ValueError, TypeError):
            return None
    
    return None

class MinecraftPaymentBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Configuration with Railway environment variable support
        self.config = {
            'discord': {
                'token': os.getenv('DISCORD_TOKEN'),
                'client_id': os.getenv('DISCORD_CLIENT_ID'),
                'authorized_users': self._parse_authorized_users()
            },
            'minecraft': {
                'host': os.getenv('MINECRAFT_HOST', 'localhost'),
                'port': int(os.getenv('MINECRAFT_PORT', '25565')),
                'username': os.getenv('MINECRAFT_USERNAME'),
                'password': os.getenv('MINECRAFT_PASSWORD'),
                'type': os.getenv('MINECRAFT_TYPE', 'Java').lower(),
                'version': os.getenv('MINECRAFT_VERSION', '1.21.70'),
                'auth': os.getenv('AUTH_TYPE', 'microsoft')
            },
            'donutsmp': {
                'api_key': os.getenv('DONUTSMP_API_KEY')
            },
            'railway': {
                'environment': os.getenv('RAILWAY_ENVIRONMENT', 'development'),
                'port': int(os.getenv('PORT', '3000'))
            }
        }
        
        # Log configuration for debugging (without sensitive data)
        logger.info(f"Bot configured for {self.config['railway']['environment']} environment")
        logger.info(f"Minecraft server: {self.config['minecraft']['host']}:{self.config['minecraft']['port']}")
        logger.info(f"Minecraft type: {self.config['minecraft']['type']}")
        logger.info(f"Authorized users count: {len(self.config['discord']['authorized_users'])}")
        
        # Minecraft connection status
        self.minecraft_connected = False
        self.minecraft_process = None
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        
        # AFK accounts management
        self.afk_accounts = {}
        self.afk_processes = {}
        self.load_afk_accounts()
        
    def load_afk_accounts(self):
        """Load AFK accounts configuration from environment variables"""
        try:
            # Try to load from environment variables first
            afk_accounts_env = os.getenv('AFK_ACCOUNTS')
            if afk_accounts_env:
                logger.info("Loading AFK accounts from environment variables")
                afk_accounts_dict = json.loads(afk_accounts_env)
                
                # Get AFK server configuration from environment (with fallbacks to main account settings)
                afk_host = os.getenv('AFK_HOST', self.config['minecraft']['host'])
                afk_port = int(os.getenv('AFK_PORT', str(self.config['minecraft']['port'])))
                afk_type = os.getenv('AFK_TYPE', self.config['minecraft']['type'])
                afk_version = os.getenv('AFK_VERSION', self.config['minecraft']['version'])
                afk_auth = os.getenv('AFK_AUTH', self.config['minecraft']['auth'])
                
                # Build the configuration structure
                afk_accounts_list = []
                for username, password in afk_accounts_dict.items():
                    account_config = {
                        "minecraft_host": afk_host,
                        "minecraft_port": afk_port,
                        "minecraft_username": username,
                        "minecraft_password": password,
                        "minecraft_type": afk_type,
                        "minecraft_version": afk_version,
                        "minecraft_authtype": afk_auth
                    }
                    afk_accounts_list.append(account_config)
                
                # Set up the main account configuration
                main_account = {
                    "minecraft_host": self.config['minecraft']['host'],
                    "minecraft_port": self.config['minecraft']['port'],
                    "minecraft_username": self.config['minecraft']['username'],
                    "minecraft_password": self.config['minecraft']['password'],
                    "minecraft_type": self.config['minecraft']['type'],
                    "minecraft_version": self.config['minecraft']['version'],
                    "minecraft_authtype": self.config['minecraft']['auth']
                }
                
                self.afk_accounts = {
                    "main_account": main_account,
                    "afk_accounts": afk_accounts_list
                }
                
                logger.info(f"Loaded {len(afk_accounts_list)} AFK accounts from environment variables")
                
            else:
                # Fallback to JSON file if environment variable not found
                logger.info("AFK_ACCOUNTS environment variable not found, trying JSON file")
                afk_config_path = os.path.join(self.project_dir, 'afk_accounts.json')
                if os.path.exists(afk_config_path):
                    with open(afk_config_path, 'r') as f:
                        config = json.load(f)
                        self.afk_accounts = config
                        logger.info(f"Loaded {len(config.get('afk_accounts', []))} AFK accounts from JSON file")
                else:
                    logger.warning("No AFK accounts configuration found (neither environment variable nor JSON file)")
                    self.afk_accounts = {"main_account": {}, "afk_accounts": []}
            
            # Clean up any old account-specific status files
            self._cleanup_old_status_files()
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AFK_ACCOUNTS JSON: {e}")
            self.afk_accounts = {"main_account": {}, "afk_accounts": []}
        except Exception as e:
            logger.error(f"Failed to load AFK accounts configuration: {e}")
            self.afk_accounts = {"main_account": {}, "afk_accounts": []}
    
    def _cleanup_old_status_files(self):
        """Clean up old account-specific status files"""
        try:
            for account in self.afk_accounts.get('afk_accounts', []):
                username = account.get('minecraft_username', '')
                if username:
                    old_status_file = os.path.join(self.project_dir, f'minecraft_status_{username}.json')
                    if os.path.exists(old_status_file):
                        try:
                            os.remove(old_status_file)
                            logger.info(f"Cleaned up old status file for {username}")
                        except:
                            pass
        except Exception as e:
            logger.error(f"Error cleaning up old status files: {e}")
    
    def _parse_authorized_users(self) -> list:
        """Parse authorized user IDs from environment variable"""
        users_str = os.getenv('AUTHORIZED_USERS', '')
        if not users_str:
            return []
        return [int(user_id.strip()) for user_id in users_str.split(',') if user_id.strip()]
    
    def _check_permissions(self, user_id: int) -> bool:
        """Check if user has permission to use bot commands"""
        return user_id in self.config['discord']['authorized_users']
    
    def _create_embed(self, title: str, description: str, color: discord.Color, user: discord.User) -> discord.Embed:
        """Create a standardized embed with user author"""
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_author(name=user.display_name, icon_url=user.avatar.url if user.avatar else None)
        return embed
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string with suffixes (M, B, T, etc.)"""
        amount_str = amount_str.upper().strip()
        
        # Remove commas
        amount_str = amount_str.replace(',', '')
        
        # Define multipliers
        multipliers = {
            'K': 1_000,
            'M': 1_000_000,
            'B': 1_000_000_000,
            'T': 1_000_000_000_000,
            'Q': 1_000_000_000_000_000
        }
        
        # Check for suffix
        if amount_str[-1] in multipliers:
            try:
                number = float(amount_str[:-1])
                return number * multipliers[amount_str[-1]]
            except ValueError:
                return None
        else:
            try:
                return float(amount_str)
            except ValueError:
                return None
    
    async def _get_player_balance(self, username: str) -> Optional[Dict[str, Any]]:
        """Get player balance from DonutSMP API"""
        if not self.config['donutsmp']['api_key']:
            logger.error("DonutSMP API key not configured")
            return None
        
        try:
            headers = {
                'Authorization': f"Bearer {self.config['donutsmp']['api_key']}",
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"https://api.donutsmp.net/v1/stats/{username}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error("DonutSMP API: Unauthorized - check your API key")
                return None
            elif response.status_code == 500:
                logger.error(f"DonutSMP API: Player {username} not found")
                return None
            else:
                logger.error(f"DonutSMP API: Unexpected status code {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"DonutSMP API request failed: {e}")
            return None
    
    async def _get_minecraft_status(self) -> Optional[Dict[str, Any]]:
        """Get Minecraft client status from status file"""
        try:
            status_file = os.path.join(self.project_dir, 'minecraft_status.json')
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to read Minecraft status: {e}")
            return None
    
    async def _send_minecraft_command(self, command: str) -> bool:
        """Send command to Minecraft client"""
        try:
            command_file = os.path.join(self.project_dir, 'minecraft_command.txt')
            with open(command_file, 'w') as f:
                f.write(command)
            return True
        except Exception as e:
            logger.error(f"Failed to send Minecraft command: {e}")
            return False
    
    async def _connect_minecraft(self) -> Dict[str, Any]:
        """Connect to Minecraft server using Node.js client"""
        try:
            if self.minecraft_connected:
                return {'success': False, 'message': 'Already connected to Minecraft server'}
            
            logger.info(f"Connecting to {self.config['minecraft']['type']} server at {self.config['minecraft']['host']}:{self.config['minecraft']['port']}")
            
            # Verify DonutSMP API connection first
            if not self.config['donutsmp']['api_key']:
                return {'success': False, 'message': 'DonutSMP API key not configured'}
            
            # Start the Node.js Minecraft client as a subprocess
            node_script = os.path.join(self.project_dir, 'minecraft_client.js')
            if not os.path.exists(node_script):
                return {'success': False, 'message': 'Minecraft client script not found'}
            
            # Kill any existing Minecraft client process
            if hasattr(self, 'minecraft_process') and self.minecraft_process:
                try:
                    self.minecraft_process.terminate()
                    self.minecraft_process.wait(timeout=5)
                except:
                    pass
            
            # Start the Minecraft client with basic configuration
            self.minecraft_process = subprocess.Popen(
                ['node', node_script, 'connect'],
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            logger.info("Minecraft client process started")
            
            # Start logging output in the background
            asyncio.create_task(self._log_process_output(self.minecraft_process))
            
            # Wait for the process to initialize
            await asyncio.sleep(3)
            
            # Check if process is still running
            if self.minecraft_process.poll() is not None:
                error_msg = f"Minecraft process failed to start (exit code: {self.minecraft_process.returncode})"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            self.minecraft_connected = True
            logger.info("Successfully connected to Minecraft")
            return {'success': True, 'message': 'Successfully connected to Minecraft server'}
            
        except Exception as e:
            logger.error(f"Failed to connect to Minecraft: {e}", exc_info=True)
            return {'success': False, 'message': f'Connection failed: {str(e)}'}
    
    async def _log_process_output(self, process):
        """Log output from the Minecraft process"""
        try:
            logger.debug("Starting to log process output")
            
            async def read_lines(stream, is_stderr=False):
                """Read lines from a stream and log them"""
                while True:
                    try:
                        line = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: stream.readline()
                        )
                        if not line:
                            if process.poll() is not None:
                                break
                            await asyncio.sleep(0.1)
                            continue
                            
                        line = line.strip()
                        if line:
                            if is_stderr:
                                logger.error(f"[Minecraft] {line}")
                            else:
                                logger.info(f"[Minecraft] {line}")
                                
                    except Exception as e:
                        if 'Bad file descriptor' in str(e) or 'I/O operation on closed file' in str(e):
                            break
                        logger.error(f"Error reading {'stderr' if is_stderr else 'stdout'}: {e}")
                        await asyncio.sleep(1)
            
            # Start reading from both streams
            tasks = [
                asyncio.create_task(read_lines(process.stdout, False)),
                asyncio.create_task(read_lines(process.stderr, True))
            ]
            
            # Wait for process to complete
            while process.poll() is None:
                try:
                    await asyncio.wait_for(asyncio.shield(asyncio.sleep(1)), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in log process: {e}")
                    break
            
            # Cancel any running tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Read any remaining output
            try:
                remaining_stdout, remaining_stderr = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: process.communicate(timeout=5)
                )
                
                if remaining_stdout and remaining_stdout.strip():
                    logger.info(f"[Minecraft] {remaining_stdout.strip()}")
                if remaining_stderr and remaining_stderr.strip():
                    logger.error(f"[Minecraft] {remaining_stderr.strip()}")
                    
            except Exception as e:
                if 'No such process' not in str(e):
                    logger.error(f"Error reading remaining output: {e}")
            
            logger.debug("Finished logging process output")
            
        except Exception as e:
            logger.error(f"Critical error in log process: {e}", exc_info=True)
    
    async def _log_afk_process_output(self, process, username):
        """Log output from an AFK Minecraft process with username prefix"""
        try:
            logger.debug(f"Starting to log AFK process output for {username}")
            
            async def read_lines(stream, is_stderr=False):
                """Read lines from a stream and log them with AFK prefix"""
                while True:
                    try:
                        line = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: stream.readline()
                        )
                        if not line:
                            if process.poll() is not None:
                                break
                            await asyncio.sleep(0.1)
                            continue
                            
                        line = line.strip()
                        if line:
                            if is_stderr:
                                logger.error(f"[AFK-{username}] {line}")
                            else:
                                logger.info(f"[AFK-{username}] {line}")
                                
                    except Exception as e:
                        if 'Bad file descriptor' in str(e) or 'I/O operation on closed file' in str(e):
                            break
                        logger.error(f"Error reading {'stderr' if is_stderr else 'stdout'} for {username}: {e}")
                        await asyncio.sleep(1)
            
            # Start reading from both streams
            tasks = [
                asyncio.create_task(read_lines(process.stdout, False)),
                asyncio.create_task(read_lines(process.stderr, True))
            ]
            
            # Wait for process to complete
            while process.poll() is None:
                try:
                    await asyncio.wait_for(asyncio.shield(asyncio.sleep(1)), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in AFK log process for {username}: {e}")
                    break
            
            # Cancel any running tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Read any remaining output
            try:
                remaining_stdout, remaining_stderr = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: process.communicate(timeout=5)
                )
                
                if remaining_stdout and remaining_stdout.strip():
                    logger.info(f"[AFK-{username}] {remaining_stdout.strip()}")
                if remaining_stderr and remaining_stderr.strip():
                    logger.error(f"[AFK-{username}] {remaining_stderr.strip()}")
                    
            except Exception as e:
                if 'No such process' not in str(e):
                    logger.error(f"Error reading remaining output for {username}: {e}")
            
            logger.debug(f"Finished logging AFK process output for {username}")
            
        except Exception as e:
            logger.error(f"Critical error in AFK log process for {username}: {e}", exc_info=True)
    
    async def _send_pay_command(self, username: str, amount_str: str) -> Dict[str, Any]:
        """Send a pay command to the Minecraft server
        
        Args:
            username: The Minecraft username to send payment to
            amount_str: The amount as a string (e.g., '10M', '5B', '1T')
        """
        logger.info(f"=== Starting payment process ===")
        logger.info(f"Recipient: {username}, Amount: {amount_str}")
        
        try:
            # Check if minecraft_process exists
            if not hasattr(self, 'minecraft_process') or not self.minecraft_process:
                error_msg = "❌ Minecraft process not found. Is the bot connected?"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            # Check if process is running
            if self.minecraft_process.poll() is not None:
                error_msg = f"❌ Minecraft process is not running (exit code: {self.minecraft_process.returncode})"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            # Parse the amount string to get the numeric value
            parsed_amount = parse_amount(amount_str)
            if parsed_amount is None:
                error_msg = f"❌ Invalid amount format: {amount_str}. Use format like 10K, 5M, 1B, etc."
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
                
            # Format the command with the numeric amount (no commas)
            numeric_amount = int(parsed_amount)
            command = f'/pay {username} {numeric_amount}'
            
            # Add debug logging
            logger.info(f"=== DEBUG PAYMENT COMMAND ===")
            logger.info(f"Command to send: '{command}'")
            logger.info(f"Original amount: {amount_str}")
            logger.info(f"Parsed amount: {numeric_amount:,}")
            
            # Write command to the expected file for the JavaScript client
            command_file = os.path.join(os.path.dirname(__file__), 'minecraft_command.txt')
            try:
                with open(command_file, 'w', encoding='utf-8') as f:
                    f.write(command)
                logger.info(f"✅ Command written to {command_file}")
                
                # The JavaScript client will pick up this file and execute the command
                # Wait a moment for the command to be processed
                await asyncio.sleep(1.5)
                
                return {
                    'success': True, 
                    'username': username, 
                    'amount': amount_str,
                    'message': f'💰 Payment of {amount_str} sent to {username}'
                }
                
            except Exception as e:
                error_msg = f"❌ Error writing to command file: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {'success': False, 'message': error_msg}
                
            except Exception as e:
                error_msg = f"❌ Unexpected error in command handling: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {'success': False, 'message': error_msg}
            
        except Exception as e:
            error_msg = f"❌ Critical error in _send_pay_command: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': 'A critical error occurred while processing payment'}
            
        finally:
            logger.info("=== Payment process completed ===\n")
    
    async def _disconnect_minecraft(self) -> Dict[str, Any]:
        """Disconnect from Minecraft server"""
        try:
            if not self.minecraft_connected:
                return {'success': False, 'message': 'Not connected to Minecraft server'}
            
            # Terminate the Minecraft client process
            if self.minecraft_process:
                self.minecraft_process.terminate()
                self.minecraft_process = None
            
            self.minecraft_connected = False
            logger.info("Disconnected from Minecraft server")
            return {'success': True, 'message': 'Successfully disconnected from Minecraft server'}
            
        except Exception as e:
            logger.error(f"Failed to disconnect from Minecraft: {e}")
            return {'success': False, 'message': f'Disconnection failed: {str(e)}'}
            
    async def _check_balance_before_payment(self, amount: float) -> Dict[str, Any]:
        """Check player balance before processing payment"""
        try:
            # Check player balance first
            balance_data = await self._get_player_balance(self.config['minecraft']['username'])
            if not balance_data:
                return {'success': False, 'message': 'Could not verify account balance'}
            
            try:
                current_balance = float(balance_data['result']['money'])
                if current_balance < amount:
                    return {'success': False, 'message': f'Insufficient funds. Current balance: {current_balance:,.2f}'}
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing balance data: {e}")
                return {'success': False, 'message': 'Could not parse balance information'}
            
            # Format the amount for the command
            if amount >= 1_000_000_000_000:
                value = amount / 1_000_000_000_000
                formatted_amount = f"{int(value)}T" if value == int(value) else f"{value:.1f}T"
            elif amount >= 1_000_000_000:
                value = amount / 1_000_000_000
                formatted_amount = f"{int(value)}B" if value == int(value) else f"{value:.1f}B"
            elif amount >= 1_000_000:
                value = amount / 1_000_000
                formatted_amount = f"{int(value)}M" if value == int(value) else f"{value:.1f}M"
            elif amount >= 1_000:
                value = amount / 1_000
                formatted_amount = f"{int(value)}K" if value == int(value) else f"{value:.1f}K"
            else:
                formatted_amount = f"{int(amount)}" if amount == int(amount) else f"{amount:.1f}"
            
            # Send the actual command to Minecraft server via Mineflayer
            command = f"/pay {username} {formatted_amount}"
            logger.info(f"Sending command: {command}")
            
            # Send command to Mineflayer client
            success = await self._send_minecraft_command(command)
            if success:
                logger.info(f"Successfully sent command to server: {command}")
                return {
                    'success': True, 
                    'message': f'Payment sent successfully',
                    'username': username,
                    'amount': formatted_amount
                }
            else:
                return {'success': False, 'message': 'Failed to send command to Minecraft client'}
            
        except Exception as e:
            logger.error(f"Failed to send pay command: {e}")
            return {'success': False, 'message': f'Payment failed: {str(e)}'}
    
    def _is_main_account(self, username: str) -> bool:
        """Check if the given username is the main account"""
        main_account_username = self.afk_accounts.get('main_account', {}).get('minecraft_username', '')
        return username == main_account_username or username == self.config['minecraft']['username']

    async def _connect_afk_account_simple(self, account_config: dict) -> dict:
        """Connect a single AFK account using the same method as main connect"""
        try:
            username = account_config['minecraft_username']
            
            # Skip main account - it's handled by /connect and /disconnect
            if self._is_main_account(username):
                logger.info(f"Skipping main account {username} - use /connect instead")
                return {'success': False, 'message': f'Skipped main account {username} - use /connect command instead'}
            
            logger.info(f"Connecting to {account_config['minecraft_type']} server at {account_config['minecraft_host']}:{account_config['minecraft_port']} as {username}")
            
            # Kill any existing process for this account
            if username in self.afk_processes and self.afk_processes[username]:
                try:
                    self.afk_processes[username].terminate()
                    self.afk_processes[username].wait(timeout=5)
                except:
                    pass
            
            # Start the Node.js Minecraft client as a subprocess
            node_script = os.path.join(self.project_dir, 'minecraft_client.js')
            if not os.path.exists(node_script):
                return {'success': False, 'message': 'Minecraft client script not found'}
            
            # Set environment variables for this account
            env = os.environ.copy()
            env['MINECRAFT_HOST'] = account_config['minecraft_host']
            env['MINECRAFT_PORT'] = str(account_config['minecraft_port'])
            env['MINECRAFT_USERNAME'] = username
            env['MINECRAFT_PASSWORD'] = account_config['minecraft_password']
            env['MINECRAFT_TYPE'] = account_config['minecraft_type']
            env['MINECRAFT_VERSION'] = account_config['minecraft_version']
            env['AUTH_TYPE'] = account_config['minecraft_authtype']
            
            # Start the Minecraft client with account-specific environment
            process = subprocess.Popen(
                ['node', node_script, 'connect'],
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                text=True,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.afk_processes[username] = process
            logger.info(f"AFK account {username} process started")
            
            # Start logging output in the background (like main connect does)
            asyncio.create_task(self._log_afk_process_output(process, username))
            
            # Wait for the process to initialize
            await asyncio.sleep(3)
            
            # Check if process is still running
            if process.poll() is not None:
                error_msg = f"AFK account {username} failed to connect (exit code: {process.returncode})"
                logger.error(error_msg)
                return {'success': False, 'message': error_msg}
            
            logger.info(f"Successfully connected AFK account: {username}")
            return {'success': True, 'message': f'Connected {username}'}
            
        except Exception as e:
            logger.error(f"Failed to connect AFK account {username}: {e}")
            return {'success': False, 'message': f'Failed to connect {username}: {str(e)}'}
    
    async def _connect_afk_account_with_afk(self, account_config: dict) -> dict:
        """Connect a single AFK account and send /warp afk"""
        result = await self._connect_afk_account_simple(account_config)
        if result['success']:
            # Wait a bit then send /warp afk command
            await asyncio.sleep(5)
            username = account_config['minecraft_username']
            try:
                command_file = os.path.join(self.project_dir, f'minecraft_command_{username}.txt')
                with open(command_file, 'w') as f:
                    f.write('/warp afk')
                logger.info(f"Sent /warp afk command to {username}")
            except Exception as e:
                logger.error(f"Failed to send /warp afk to {username}: {e}")
        return result
    
    async def _disconnect_afk_account_simple(self, username: str) -> dict:
        """Disconnect a single AFK account"""
        try:
            # Skip main account - it's handled by /connect and /disconnect
            if self._is_main_account(username):
                logger.info(f"Skipping main account {username} - use /disconnect instead")
                return {'success': False, 'message': f'Skipped main account {username} - use /disconnect command instead'}
            
            if username in self.afk_processes and self.afk_processes[username]:
                process = self.afk_processes[username]
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                del self.afk_processes[username]
                
                # Clean up command files and any old status files
                files_to_cleanup = [
                    f'minecraft_command_{username}.txt',
                    f'minecraft_status_{username}.json'  # Clean up old account-specific status files
                ]
                
                for filename in files_to_cleanup:
                    file_path = os.path.join(self.project_dir, filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except:
                            pass
                
                logger.info(f"Disconnected AFK account: {username}")
                return {'success': True, 'message': f'Disconnected {username}'}
            else:
                return {'success': False, 'message': f'{username} was not connected'}
                
        except Exception as e:
            logger.error(f"Failed to disconnect AFK account {username}: {e}")
            return {'success': False, 'message': f'Failed to disconnect {username}: {str(e)}'}
    
    async def _get_afk_account_status(self, username: str) -> dict:
        """Get status of a single AFK account"""
        # Skip main account - it's handled by /connect and /disconnect
        if self._is_main_account(username):
            return {'username': username, 'status': 'Main Account (use /status command)', 'connected': False}
        
        if username in self.afk_processes and self.afk_processes[username]:
            process = self.afk_processes[username]
            if process.poll() is None:
                return {'username': username, 'status': 'Connected', 'connected': True}
            else:
                return {'username': username, 'status': 'Disconnected (Process ended)', 'connected': False}
        else:
            return {'username': username, 'status': 'Disconnected', 'connected': False}
    
    async def _send_minecraft_whisper_to_drglaze(self, message: str = "hello"):
        """Send a Minecraft whisper to DrGlaze"""
        try:
            # Send /w DrGlaze message through the main account if connected
            if self.minecraft_connected and self.minecraft_process and self.minecraft_process.poll() is None:
                command = f"/w DrGlaze {message}"
                command_file = os.path.join(self.project_dir, 'minecraft_command.txt')
                with open(command_file, 'w') as f:
                    f.write(command)
                logger.info(f"Sent Minecraft whisper to DrGlaze: {command}")
            else:
                logger.warning("Main account not connected, cannot send whisper to DrGlaze")
        except Exception as e:
            logger.error(f"Failed to send Minecraft whisper to DrGlaze: {e}")

    async def setup_health_check_server(self):
        """Setup health check web server for Railway"""
        try:
            async def health_check(request):
                """Health check endpoint"""
                status = {
                    'status': 'healthy',
                    'bot_ready': self.is_ready(),
                    'minecraft_connected': self.minecraft_connected,
                    'timestamp': time.time()
                }
                return web.json_response(status)
            
            app = web.Application()
            app.router.add_get('/health', health_check)
            app.router.add_get('/', health_check)  # Root endpoint for Railway
            
            port = self.config['railway']['port']
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            
            logger.info(f"Health check server started on port {port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")

    async def on_ready(self):
        """Bot ready event"""
        logger.info(f'Bot logged in as {self.user}')
        
        # Start health check server for Railway
        if self.config['railway']['environment'] == 'production':
            await self.setup_health_check_server()
        
        # Load gambling cog first
        try:
            await self.load_extension('gambling')
            logger.info('Loaded gambling cog')
        except Exception as e:
            logger.error(f'Failed to load gambling cog: {e}', exc_info=True)
        
        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} command(s)')
        except Exception as e:
            logger.error(f'Failed to sync commands: {e}')

# AFK command group (defined before bot creation)
afk_group = app_commands.Group(name="afk", description="AFK account management")

# Create bot instance
bot = MinecraftPaymentBot()

# Add AFK command group to bot
bot.tree.add_command(afk_group)

@bot.tree.command(name="connect", description="Connect to minecraft")
async def connect_command(interaction: discord.Interaction):
    """Connect to Minecraft server"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "Warning - Insufficient Permissions",
            "You do not have access to this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        result = await bot._connect_minecraft()
        
        if result['success']:
            embed = bot._create_embed(
                "Connected",
                "Successfully connected.",
                discord.Color.dark_blue(),
                interaction.user
            )
        else:
            embed = bot._create_embed(
                "Warning - Error",
                "A error occured while running this command. Please try again.",
                discord.Color.dark_gold(),
                interaction.user
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Connect command error: {e}")
        embed = bot._create_embed(
            "Warning - Error",
            "A error occured while running this command. Please try again.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="disconnect", description="Disconnect from minecraft")
async def disconnect_command(interaction: discord.Interaction):
    """Disconnect from Minecraft server"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "Warning - Insufficient Permissions",
            "You do not have access to this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Defer the response first
    await interaction.response.defer()
    
    try:
        result = await bot._disconnect_minecraft()
        
        if result['success']:
            embed = bot._create_embed(
                "✅ Disconnected",
                "Successfully disconnected from the Minecraft server.",
                discord.Color.dark_blue(),
                interaction.user
            )
        else:
            embed = bot._create_embed(
                "❌ Error",
                result.get('message', 'Failed to disconnect from the Minecraft server.'),
                discord.Color.dark_gold(),
                interaction.user
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Disconnect command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while disconnecting: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="pay", description="Pay a specific user")
@app_commands.describe(
    amount="The amount you wish to pay the user (supports 20M, 20B, 20T, etc.)",
    username="The username you wish to pay"
)
async def pay_command(interaction: discord.Interaction, amount: str, username: str):
    """Send payment to a user"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "⚠️ Insufficient Permissions",
            "You do not have permission to use this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Defer the response first
    await interaction.response.defer()
    
    try:
        # Check if Minecraft client is connected
        if not bot.minecraft_connected or not bot.minecraft_process or bot.minecraft_process.poll() is not None:
            embed = bot._create_embed(
                "⚠️ Not Connected",
                "The bot is not connected to the Minecraft server. Use `/connect` first.",
                discord.Color.dark_gold(),
                interaction.user
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Parse amount
        parsed_amount = bot._parse_amount(amount)
        if parsed_amount is None or parsed_amount <= 0:
            embed = bot._create_embed(
                "❌ Invalid Amount",
                "Please specify a valid positive number (supports K, M, B, T suffixes).\nExample: 1M, 2.5B, 100T",
                discord.Color.dark_gold(),
                interaction.user
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Format the amount with commas for display
        formatted_amount = "{:,}".format(int(parsed_amount)) if parsed_amount.is_integer() else "{:,.2f}".format(parsed_amount)
        
        # Send payment with the original amount string (e.g., '10M', '5B')
        logger.info(f"Attempting to pay {username} amount {amount}")
        result = await bot._send_pay_command(username, amount)
        
        if result.get('success', False):
            embed = bot._create_embed(
                "💰 Payment Sent",
                f"Successfully sent **{formatted_amount}** to **{result.get('username', username)}**",
                discord.Color.dark_blue(),
                interaction.user
            )
        else:
            error_msg = result.get('message', 'Unknown error occurred')
            embed = bot._create_embed(
                "❌ Payment Failed",
                f"Failed to send payment: {error_msg}",
                discord.Color.dark_red(),
                interaction.user
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Pay command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while processing your payment: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Check the bot connection status")
async def status_command(interaction: discord.Interaction):
    """Check bot status"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "Warning - Insufficient Permissions",
            "You do not have access to this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        status = "Connected" if bot.minecraft_connected else "Disconnected"
        server_info = f"{bot.config['minecraft']['host']}:{bot.config['minecraft']['port']}" if bot.minecraft_connected else "N/A"
        minecraft_type = bot.config['minecraft']['type'].title()
        
        description = f"**Bot Status:**\n🤖 Discord: Connected\n⛏️ Minecraft: {status}\n🌐 Server: {server_info}\n📦 Type: {minecraft_type}"
        
        embed = bot._create_embed(
            "Bot Status",
            description,
            discord.Color.blue(),
            interaction.user
        )
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Status command error: {e}")
        embed = bot._create_embed(
            "Warning - Error",
            "A error occured while running this command. Please try again.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed)

@afk_group.command(name="connect", description="Connect all AFK accounts")
async def afk_connect_command(interaction: discord.Interaction):
    """Connect all AFK accounts without /afk 40"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "⚠️ Insufficient Permissions",
            "You do not have permission to use this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        afk_accounts = bot.afk_accounts.get('afk_accounts', [])
        if not afk_accounts:
            embed = bot._create_embed(
                "❌ No AFK Accounts",
                "No AFK accounts configured.",
                discord.Color.dark_red(),
                interaction.user
            )
            await interaction.followup.send(embed=embed)
            return
        
        # AFK accounts will connect automatically
        
        results = []
        for account in afk_accounts:
            username = account['minecraft_username']
            # Skip main account
            if bot._is_main_account(username):
                results.append(f"• {username}: ⚠️ Main Account (use /connect)")
                continue
                
            result = await bot._connect_afk_account_simple(account)
            results.append(f"• {username}: {'✅' if result['success'] else '❌'}")
        
        embed = bot._create_embed(
            "🔗 AFK Connect",
            f"AFK accounts status:\n" + "\n".join(results),
            discord.Color.dark_blue(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"AFK connect command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while connecting AFK accounts: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@afk_group.command(name="on", description="Connect all AFK accounts and run /warp afk")
async def afk_on_command(interaction: discord.Interaction):
    """Connect all AFK accounts and run /warp afk"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "⚠️ Insufficient Permissions",
            "You do not have permission to use this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        afk_accounts = bot.afk_accounts.get('afk_accounts', [])
        if not afk_accounts:
            embed = bot._create_embed(
                "❌ No AFK Accounts",
                "No AFK accounts configured.",
                discord.Color.dark_red(),
                interaction.user
            )
            await interaction.followup.send(embed=embed)
            return
        
        # AFK accounts will connect and run /warp afk automatically
        
        results = []
        for account in afk_accounts:
            username = account['minecraft_username']
            # Skip main account
            if bot._is_main_account(username):
                results.append(f"• {username}: ⚠️ Main Account (use /connect)")
                continue
                
            result = await bot._connect_afk_account_with_afk(account)
            results.append(f"• {username}: {'✅' if result['success'] else '❌'}")
        
        embed = bot._create_embed(
            "💤 AFK On",
            f"AFK accounts with /warp afk:\n" + "\n".join(results),
            discord.Color.dark_blue(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"AFK on command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while starting AFK accounts: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@afk_group.command(name="disconnect", description="Disconnect all AFK accounts")
async def afk_disconnect_command(interaction: discord.Interaction):
    """Disconnect all AFK accounts"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "⚠️ Insufficient Permissions",
            "You do not have permission to use this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        afk_accounts = bot.afk_accounts.get('afk_accounts', [])
        if not afk_accounts:
            embed = bot._create_embed(
                "❌ No AFK Accounts",
                "No AFK accounts configured.",
                discord.Color.dark_red(),
                interaction.user
            )
            await interaction.followup.send(embed=embed)
            return
        
        results = []
        for account in afk_accounts:
            username = account['minecraft_username']
            # Skip main account
            if bot._is_main_account(username):
                results.append(f"• {username}: ⚠️ Main Account (use /disconnect)")
                continue
                
            result = await bot._disconnect_afk_account_simple(username)
            results.append(f"• {username}: {'✅' if result['success'] else '❌'}")
        
        embed = bot._create_embed(
            "🔌 AFK Disconnect",
            f"AFK accounts status:\n" + "\n".join(results),
            discord.Color.dark_blue(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"AFK disconnect command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while disconnecting AFK accounts: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.followup.send(embed=embed)

@afk_group.command(name="status", description="Check status of all AFK accounts")
async def afk_status_command(interaction: discord.Interaction):
    """Check status of all AFK accounts"""
    user_id = interaction.user.id
    
    # Check permissions
    if not bot._check_permissions(user_id):
        embed = bot._create_embed(
            "⚠️ Insufficient Permissions",
            "You do not have permission to use this command.",
            discord.Color.dark_gold(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        afk_accounts = bot.afk_accounts.get('afk_accounts', [])
        if not afk_accounts:
            embed = bot._create_embed(
                "❌ No AFK Accounts",
                "No AFK accounts configured.",
                discord.Color.dark_red(),
                interaction.user
            )
            await interaction.response.send_message(embed=embed)
            return
        
        status_lines = []
        connected_count = 0
        total_afk_accounts = 0
        
        for account in afk_accounts:
            username = account['minecraft_username']
            status_info = await bot._get_afk_account_status(username)
            
            if bot._is_main_account(username):
                status_emoji = "⚠️"
                status_lines.append(f"{status_emoji} **{username}**: {status_info['status']}")
            else:
                total_afk_accounts += 1
                status_emoji = "🟢" if status_info['connected'] else "🔴"
                status_lines.append(f"{status_emoji} **{username}**: {status_info['status']}")
                if status_info['connected']:
                    connected_count += 1
        
        embed = bot._create_embed(
            "📊 AFK Status",
            f"**AFK Accounts Connected: {connected_count}/{total_afk_accounts}**\n\n" + "\n".join(status_lines),
            discord.Color.blue(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"AFK status command error: {e}", exc_info=True)
        embed = bot._create_embed(
            "❌ Error",
            f"An error occurred while checking AFK status: {str(e)}",
            discord.Color.dark_red(),
            interaction.user
        )
        await interaction.response.send_message(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    logger.error(f"Command error: {error}")

# Run the bot
if __name__ == "__main__":
    if not bot.config['discord']['token']:
        logger.error("Discord token not found in environment variables")
        exit(1)
    
    if not bot.config['discord']['authorized_users']:
        logger.warning("No authorized users configured - bot commands will be inaccessible")
    
    try:
        bot.run(bot.config['discord']['token'])
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)
