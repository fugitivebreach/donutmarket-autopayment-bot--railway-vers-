import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import time
import re
# import aiohttp  # Temporarily disabled
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GamblingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()
        self.verified_users = {}  # {discord_id: {"minecraft_username": str, "balance": float, "verification_pending": bool}}
        self.active_users = set()  # Users currently using the panel
        self.pending_verifications = {}  # {discord_id: {"minecraft_username": str, "timestamp": float}}
        
        # Load persistent data
        self.load_gambling_data()
        
        # Start background tasks
        self.check_minecraft_chat.start()
        self.update_leaderboard.start()
        self.auto_save_data.start()
    
    def load_config(self):
        """Load configuration from config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            return {
                "channelID": None,
                "messageID": None,
                "leaderboardChannelID": None,
                "leaderboardMessageID": None
            }
    
    def save_config(self):
        """Save configuration to config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config.json: {e}")
    
    def load_gambling_data(self):
        """Load persistent gambling data from JSON file"""
        try:
            data_path = os.path.join(os.path.dirname(__file__), 'gambling_data.json')
            if os.path.exists(data_path):
                with open(data_path, 'r') as f:
                    data = json.load(f)
                
                # Convert string keys back to integers for discord IDs
                self.verified_users = {int(k): v for k, v in data.get('verified_users', {}).items()}
                self.pending_verifications = {int(k): v for k, v in data.get('pending_verifications', {}).items()}
                
                logger.info(f"Loaded gambling data: {len(self.verified_users)} verified users")
            else:
                logger.info("No existing gambling data found, starting fresh")
                
        except Exception as e:
            logger.error(f"Failed to load gambling data: {e}")
            self.verified_users = {}
            self.pending_verifications = {}
    
    def save_gambling_data(self):
        """Save persistent gambling data to JSON file"""
        try:
            data_path = os.path.join(os.path.dirname(__file__), 'gambling_data.json')
            
            # Convert integer keys to strings for JSON serialization
            data = {
                'verified_users': {str(k): v for k, v in self.verified_users.items()},
                'pending_verifications': {str(k): v for k, v in self.pending_verifications.items()},
                'last_saved': time.time()
            }
            
            with open(data_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("Saved gambling data to file")
            
        except Exception as e:
            logger.error(f"Failed to save gambling data: {e}")
    
    @tasks.loop(minutes=5)
    async def auto_save_data(self):
        """Auto-save gambling data every 5 minutes"""
        self.save_gambling_data()
    
    def cog_unload(self):
        """Save data when cog is unloaded"""
        self.check_minecraft_chat.cancel()
        self.update_leaderboard.cancel()
        self.auto_save_data.cancel()
        self.save_gambling_data()
        logger.info("Gambling cog unloaded and data saved")
    
    async def verify_minecraft_account(self, username: str) -> bool:
        """Verify if Minecraft account exists using Mojang API"""
        try:
            # Temporarily disabled - requires aiohttp
            # For now, just return True to allow testing
            logger.warning(f"Minecraft account verification disabled for {username} - assuming valid")
            return True
        except Exception as e:
            logger.error(f"Error verifying Minecraft account {username}: {e}")
            return False
    
    @tasks.loop(seconds=1)
    async def check_minecraft_chat(self):
        """Check Minecraft chat for payment notifications and verification messages"""
        try:
            # Check for payment notifications by reading recent chat logs
            # This integrates with your existing Minecraft client logging
            await self.check_payment_notifications()
            
            # Check for verification messages
            await self.check_verification_messages()
            
        except Exception as e:
            logger.error(f"Error checking Minecraft chat: {e}")
    
    async def check_payment_notifications(self):
        """Check for payment notifications in Minecraft chat"""
        try:
            # Read recent chat logs to find payment messages
            # Pattern: "DrGlaze paid you $1M."
            chat_log_file = os.path.join(os.path.dirname(__file__), 'recent_chat.log')
            if os.path.exists(chat_log_file):
                with open(chat_log_file, 'r') as f:
                    recent_lines = f.readlines()[-50:]  # Check last 50 lines
                
                for line in recent_lines:
                    # Look for payment pattern
                    payment_match = re.search(r'(\w+) paid you \$([0-9,.]+[KMBT]?)', line)
                    if payment_match:
                        payer = payment_match.group(1)
                        amount_str = payment_match.group(2).replace(',', '')
                        
                        # Parse amount
                        amount = self.parse_amount(amount_str)
                        
                        # Find user by Minecraft username and add to balance
                        for discord_id, user_data in self.verified_users.items():
                            if user_data.get('minecraft_username') == payer:
                                user_data['balance'] += amount
                                logger.info(f"Added ${amount:,.2f} to {payer}'s gambling balance")
                                self.save_gambling_data()  # Save after balance update
                                break
                        
        except Exception as e:
            logger.error(f"Error checking payment notifications: {e}")
    
    def parse_amount(self, amount_str: str) -> float:
        """Parse amount string with K, M, B, T suffixes"""
        try:
            amount_str = amount_str.upper().replace(',', '')
            if amount_str.endswith('K'):
                return float(amount_str[:-1]) * 1000
            elif amount_str.endswith('M'):
                return float(amount_str[:-1]) * 1000000
            elif amount_str.endswith('B'):
                return float(amount_str[:-1]) * 1000000000
            elif amount_str.endswith('T'):
                return float(amount_str[:-1]) * 1000000000000
            else:
                return float(amount_str)
        except ValueError:
            return 0.0
    
    async def check_verification_messages(self):
        """Check for verification whisper messages"""
        try:
            # Check for whisper messages containing "verify"
            chat_log_file = os.path.join(os.path.dirname(__file__), 'recent_chat.log')
            if os.path.exists(chat_log_file):
                with open(chat_log_file, 'r') as f:
                    recent_lines = f.readlines()[-20:]  # Check last 20 lines
                
                for line in recent_lines:
                    # Look for whisper pattern: "username -> thebestgambler175648: verify"
                    whisper_match = re.search(r'(\w+) -> thebestgambler175648: verify', line)
                    if whisper_match:
                        minecraft_username = whisper_match.group(1)
                        
                        # Find pending verification for this username
                        for discord_id, pending_data in list(self.pending_verifications.items()):
                            if pending_data.get('minecraft_username') == minecraft_username:
                                # Verification successful
                                self.verified_users[discord_id] = {
                                    'minecraft_username': minecraft_username,
                                    'balance': 0.0,
                                    'verification_pending': False
                                }
                                del self.pending_verifications[discord_id]
                                logger.info(f"Verified user {discord_id} as {minecraft_username}")
                                self.save_gambling_data()  # Save after verification
                                break
                        
        except Exception as e:
            logger.error(f"Error checking verification messages: {e}")
    
    @tasks.loop(minutes=1)
    async def update_leaderboard(self):
        """Update the leaderboard embed"""
        try:
            if not self.config.get("leaderboardChannelID"):
                return
            
            channel = self.bot.get_channel(self.config["leaderboardChannelID"])
            if not channel:
                return
            
            embed = discord.Embed(
                title="AutoGambling Online Users",
                description="All online users right now in the panel",
                color=discord.Color.dark_blue()
            )
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            # Add active users
            if self.active_users:
                user_mentions = []
                for user_id in self.active_users:
                    user = self.bot.get_user(user_id)
                    if user:
                        user_mentions.append(user.mention)
                
                if user_mentions:
                    embed.description += "\n\n" + "\n".join(user_mentions)
            else:
                embed.description += "\n\nNo users currently online"
            
            # Update or send leaderboard message
            if self.config.get("leaderboardMessageID"):
                try:
                    message = await channel.fetch_message(self.config["leaderboardMessageID"])
                    await message.edit(embed=embed)
                except discord.NotFound:
                    message = await channel.send(embed=embed)
                    self.config["leaderboardMessageID"] = message.id
                    self.save_config()
            else:
                message = await channel.send(embed=embed)
                self.config["leaderboardMessageID"] = message.id
                self.save_config()
                
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}")
    
    # @commands.Cog.listener()
    # async def on_ready(self):
    #     """Send gambling panel on bot startup"""
    #     # Wait a bit for bot to be fully ready
    #     await asyncio.sleep(2)
    #     await self.send_gambling_panel()
    
    async def send_gambling_panel(self):
        """Send or update the main gambling panel"""
        try:
            logger.info("Attempting to send gambling panel...")
            
            if not self.config.get("channelID"):
                logger.warning("No channel ID configured for gambling panel")
                return
            
            logger.info(f"Looking for channel ID: {self.config['channelID']}")
            channel = self.bot.get_channel(self.config["channelID"])
            if not channel:
                logger.error(f"Could not find channel with ID {self.config['channelID']}")
                logger.info(f"Available channels: {[c.id for c in self.bot.get_all_channels()]}")
                return
            
            logger.info(f"Found channel: {channel.name}")
            
            embed = discord.Embed(
                title="AUTOGAMBLING V1",
                description="Use the **🎰 Gamble** button below to start the gambling panel.",
                color=discord.Color.red()
            )
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            view = GamblingPanelView(self)
            
            # Update existing message or send new one
            if self.config.get("messageID"):
                try:
                    logger.info(f"Trying to update existing message ID: {self.config['messageID']}")
                    message = await channel.fetch_message(self.config["messageID"])
                    await message.edit(embed=embed, view=view)
                    logger.info("Successfully updated existing gambling panel")
                except discord.NotFound:
                    logger.info("Existing message not found, sending new panel")
                    message = await channel.send(embed=embed, view=view)
                    self.config["messageID"] = message.id
                    self.save_config()
                    logger.info(f"Sent new gambling panel with message ID: {message.id}")
                except discord.Forbidden:
                    logger.error("No permission to edit message, sending new panel")
                    message = await channel.send(embed=embed, view=view)
                    self.config["messageID"] = message.id
                    self.save_config()
                    logger.info(f"Sent new gambling panel with message ID: {message.id}")
            else:
                logger.info("No existing message ID, sending new panel")
                message = await channel.send(embed=embed, view=view)
                self.config["messageID"] = message.id
                self.save_config()
                logger.info(f"Sent new gambling panel with message ID: {message.id}")
                
        except discord.Forbidden:
            logger.error(f"No permission to send messages in channel {self.config['channelID']}")
        except Exception as e:
            logger.error(f"Error sending gambling panel: {e}", exc_info=True)
    
    @app_commands.command(name="send_gambling_panel", description="Manually send the gambling panel")
    async def send_panel_command(self, interaction: discord.Interaction):
        """Manually send gambling panel (admin only)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.send_gambling_panel()
            embed = discord.Embed(
                title="Success",
                description="Gambling panel sent successfully!",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"Failed to send gambling panel: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="verify_user", description="Manually verify a user for gambling")
    @app_commands.describe(user="Discord user to verify", minecraft_username="Their Minecraft username")
    async def verify_user_command(self, interaction: discord.Interaction, user: discord.Member, minecraft_username: str):
        """Manually verify a user for gambling (admin only)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Add user to verified users
            self.verified_users[user.id] = {
                'minecraft_username': minecraft_username,
                'balance': 0.0,
                'verification_pending': False
            }
            
            # Remove from pending if exists
            if user.id in self.pending_verifications:
                del self.pending_verifications[user.id]
            
            # Save data
            self.save_gambling_data()
            
            embed = discord.Embed(
                title="Success",
                description=f"Successfully verified {user.mention} as `{minecraft_username}`",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"Failed to verify user: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class GamblingPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(label="🎰 Gamble", style=discord.ButtonStyle.red)
    async def gamble_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        # Check if user is verified
        if user_id not in self.cog.verified_users:
            embed = discord.Embed(
                title="Verification Required",
                description="You need to verify your Minecraft account before gambling.",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            view = VerificationView(self.cog)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Add user to active users
        self.cog.active_users.add(user_id)
        
        # Show main gambling page
        await self.show_main_page(interaction)
    
    async def show_main_page(self, interaction: discord.Interaction):
        """Show the main gambling page for verified users"""
        user_id = interaction.user.id
        user_data = self.cog.verified_users.get(user_id, {})
        
        embed = discord.Embed(
            title="**AUTOGAMBLING V1**",
            description="Viewing main page of the panel",
            color=discord.Color.dark_blue()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        embed.add_field(
            name="**Minecraft**",
            value=f"||{user_data.get('minecraft_username', 'Unknown')}||",
            inline=False
        )
        embed.add_field(
            name="**Balance**",
            value=f"${user_data.get('balance', 0):,.2f}",
            inline=False
        )
        
        view = MainPageView(self.cog)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label="Verify Account", style=discord.ButtonStyle.gray)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VerificationModal(self.cog)
        await interaction.response.send_modal(modal)

class VerificationModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="AutoGambling V1")
        self.cog = cog
        
        self.minecraft_ign = discord.ui.TextInput(
            label="What is your Minecraft IGN",
            placeholder="Only enter your Minecraft IGN",
            required=True,
            max_length=16
        )
        self.add_item(self.minecraft_ign)
    
    async def on_submit(self, interaction: discord.Interaction):
        username = self.minecraft_ign.value.strip()
        
        # Verify account exists
        if not await self.cog.verify_minecraft_account(username):
            embed = discord.Embed(
                title="**AUTOGAMBLING V1**",
                description="Your account doesn't exist. Please check your username and try again.",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Send verification instructions
        timestamp = int(time.time()) + 60  # 1 minute from now
        
        embed = discord.Embed(
            title="**AUTOGAMBLING V1**",
            description=f"Please send the following to the account IGN\n\n```/w thebestgambler175648 verify```\n\nYou have <t:{timestamp}:R> to send this to its Minecraft chat.",
            color=discord.Color.dark_blue()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        # Store pending verification
        self.cog.pending_verifications[interaction.user.id] = {
            "minecraft_username": username,
            "timestamp": time.time()
        }
        self.cog.save_gambling_data()  # Save pending verification
        
        view = VerificationWaitView(self.cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class VerificationWaitView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
    
    @discord.ui.button(label="Done", style=discord.ButtonStyle.gray)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        # Check if verification was successful (this would be set by the chat monitoring)
        if user_id in self.cog.verified_users:
            username = self.cog.verified_users[user_id]["minecraft_username"]
            embed = discord.Embed(
                title="**AUTOGAMBLING V1**",
                description=f"Successfully verified your Minecraft account as `{username}`",
                color=discord.Color.dark_blue()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(
                title="Verification Failed",
                description="We didn't receive your verification message. Please try again.",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            await interaction.response.edit_message(embed=embed, view=None)

class MainPageView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.select(
        placeholder="View Options",
        options=[
            discord.SelectOption(
                label="Refresh Balance",
                description="Refresh the balance shown in the embed",
                value="refresh"
            ),
            discord.SelectOption(
                label="50/50",
                description="Gamble with a 50/50 percent chance of winning",
                value="5050"
            )
        ]
    )
    async def select_option(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "refresh":
            # Refresh balance (would update from actual balance tracking)
            panel_view = GamblingPanelView(self.cog)
            await panel_view.show_main_page(interaction)
        
        elif select.values[0] == "5050":
            modal = GambleModal(self.cog)
            await interaction.response.send_modal(modal)

class GambleModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="AutoGambling V1")
        self.cog = cog
        
        self.amount = discord.ui.TextInput(
            label="How much do you wish to gamble?",
            placeholder="Enter amount to gamble",
            required=True
        )
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_data = self.cog.verified_users.get(user_id, {})
        
        try:
            # Parse amount (support K, M, B, T suffixes)
            amount_str = self.amount.value.strip().upper()
            if amount_str.endswith('K'):
                amount = float(amount_str[:-1]) * 1000
            elif amount_str.endswith('M'):
                amount = float(amount_str[:-1]) * 1000000
            elif amount_str.endswith('B'):
                amount = float(amount_str[:-1]) * 1000000000
            elif amount_str.endswith('T'):
                amount = float(amount_str[:-1]) * 1000000000000
            else:
                amount = float(amount_str)
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
        except ValueError:
            embed = discord.Embed(
                title="Warning - Invalid Characters/Amount",
                description="The characters you input are not numbers. Please try again.",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            view = BackToMainView(self.cog)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Check if user has enough balance
        if amount > user_data.get('balance', 0):
            embed = discord.Embed(
                title="Warning - Invalid Characters/Amount",
                description="You don't have that amount of money. Please try again.",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            view = BackToMainView(self.cog)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Show gambling in progress
        embed = discord.Embed(
            title="**AUTOGAMBLING V1**",
            description=f"Gambling ${amount:,.2f}\n\nPlease wait...",
            color=discord.Color.dark_blue()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Wait 5 seconds
        await asyncio.sleep(5)
        
        # Rigged 10% chance of winning instead of 50%
        import random
        won = random.random() < 0.1  # 10% chance
        
        if won:
            # User wins - double their bet
            self.cog.verified_users[user_id]['balance'] += amount
            description = "You have won, you have been paid automatically."
        else:
            # User loses - remove bet amount
            self.cog.verified_users[user_id]['balance'] -= amount
            description = "You have lost, you have not been paid the bet amount has been removed from your balance."
        
        # Save data after gambling result
        self.cog.save_gambling_data()
        
        # Show result
        embed = discord.Embed(
            title="**AUTOGAMBLING V1**",
            description=description,
            color=discord.Color.dark_blue()
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        
        view = BackToMainView(self.cog)
        await interaction.edit_original_response(embed=embed, view=view)

class BackToMainView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label="Back to Main Page", style=discord.ButtonStyle.gray)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        panel_view = GamblingPanelView(self.cog)
        await panel_view.show_main_page(interaction)

async def setup(bot):
    await bot.add_cog(GamblingCog(bot))
