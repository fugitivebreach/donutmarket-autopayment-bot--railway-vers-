#!/usr/bin/env python3
"""
Startup script for Railway deployment that handles both Python and Node.js processes
"""
import os
import sys
import subprocess
import signal
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        
    def start_nodejs_process(self):
        """Start the Node.js Minecraft client process"""
        try:
            logger.info("Installing Node.js dependencies...")
            # Install Node.js dependencies first
            install_result = subprocess.run(
                ['npm', 'install'], 
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True
            )
            
            if install_result.returncode != 0:
                logger.error(f"Failed to install Node.js dependencies: {install_result.stderr}")
                return False
                
            logger.info("Node.js dependencies installed successfully")
            logger.info("Starting Node.js Minecraft client...")
            
            # Start the Node.js process in the background
            process = subprocess.Popen(
                ['node', 'minecraft_client.js', 'connect'],
                cwd=Path(__file__).parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes['nodejs'] = process
            logger.info(f"Node.js process started with PID: {process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Node.js process: {e}")
            return False
    
    def start_python_bot(self):
        """Start the Python Discord bot"""
        try:
            logger.info("Starting Python Discord bot...")
            
            # Import and run the bot
            from bot import bot
            
            # Run the bot in a separate thread/process
            import threading
            
            def run_bot():
                try:
                    if not bot.config['discord']['token']:
                        logger.error("Discord token not found in environment variables")
                        return
                    
                    if not bot.config['discord']['authorized_users']:
                        logger.warning("No authorized users configured - bot commands will be inaccessible")
                    
                    bot.run(bot.config['discord']['token'])
                except Exception as e:
                    logger.error(f"Failed to start Discord bot: {e}")
            
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            
            logger.info("Python Discord bot started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Python bot: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor running processes and restart if needed"""
        while self.running:
            try:
                # Check Node.js process
                if 'nodejs' in self.processes:
                    process = self.processes['nodejs']
                    if process.poll() is not None:
                        logger.warning(f"Node.js process died with exit code: {process.returncode}")
                        # Restart Node.js process
                        if self.start_nodejs_process():
                            logger.info("Node.js process restarted successfully")
                        else:
                            logger.error("Failed to restart Node.js process")
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                time.sleep(5)
    
    def shutdown(self):
        """Gracefully shutdown all processes"""
        logger.info("Shutting down processes...")
        self.running = False
        
        for name, process in self.processes.items():
            try:
                logger.info(f"Terminating {name} process...")
                process.terminate()
                process.wait(timeout=10)
                logger.info(f"{name} process terminated")
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {name} process...")
                process.kill()
            except Exception as e:
                logger.error(f"Error shutting down {name} process: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if hasattr(signal_handler, 'manager'):
        signal_handler.manager.shutdown()
    sys.exit(0)

def main():
    """Main startup function"""
    logger.info("Starting DonutMarket Autopayment Bot for Railway...")
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create process manager
    manager = ProcessManager()
    signal_handler.manager = manager
    
    try:
        # Start Node.js process first (Minecraft client)
        if not manager.start_nodejs_process():
            logger.error("Failed to start Node.js process, exiting...")
            return 1
        
        # Wait a bit for Node.js to initialize
        time.sleep(3)
        
        # Start Python Discord bot
        if not manager.start_python_bot():
            logger.error("Failed to start Python bot, exiting...")
            return 1
        
        logger.info("All processes started successfully!")
        logger.info("Bot is now running on Railway...")
        
        # Monitor processes
        manager.monitor_processes()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        manager.shutdown()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
