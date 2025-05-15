import logging
import asyncio
import time
from django.core.management.base import BaseCommand
from django.db import DatabaseError
from apps.chatbot.management.telegram_manager import TelegramBotManager
from apps.chatbot.models import Messenger

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Runs all Telegram bots configured in the system'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shutdown_flag = False
        self.bot_managers = []

    def handle(self, *args, **options):
        self.stdout.write("Starting Telegram bot manager...")
        
        # Configure logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                logging.FileHandler('telegram_bot_manager.log'),
                logging.StreamHandler()
            ]
        )
        logging.getLogger('httpx').setLevel(logging.WARNING)
        
        # Set up signal handler for graceful shutdown
        import signal
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Main loop that keeps running
        while not self.shutdown_flag:
            try:
                self.run_bot_manager()
                
                # If no bots were initialized, wait before checking again
                if not self.bot_managers:
                    self.stdout.write("Waiting for Telegram bots to be configured...")
                    time.sleep(60)  # Check every minute for new bots
                else:
                    # If bots are running, just keep the loop alive
                    while not self.shutdown_flag:
                        time.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error in bot manager main loop: {str(e)}", exc_info=True)
                time.sleep(30)  # Wait before retrying after error
                
        self.stdout.write("Telegram bot manager stopped.")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.stdout.write(f"Received signal {signum}, shutting down...")
        self.shutdown_flag = True
        self.shutdown_bots()

    def run_bot_manager(self):
        """Initialize and run the bot manager"""
        try:
            # Get active messengers
            messengers = Messenger.objects.filter(
                messenger_type='telegram',
                is_active=True
            ).select_related('dashboard')
            
            if not messengers.exists():
                self.stdout.write("No active Telegram messengers found.")
                return
                
            self.stdout.write(f"Found {len(messengers)} active Telegram messenger(s)")
            
            # Create event loop for this iteration
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Initialize all bots
            current_bot_managers = []
            for messenger in messengers:
                # Skip if we already have a manager for this messenger
                if any(m.messenger.id == messenger.id for m in self.bot_managers):
                    continue
                    
                manager = TelegramBotManager(messenger)
                if loop.run_until_complete(manager.initialize()):
                    current_bot_managers.append(manager)
                    self.bot_managers.append(manager)
                    self.stdout.write(f"✓ Bot for {messenger.dashboard.name} initialized")
                else:
                    self.stdout.write(f"× Failed to initialize bot for {messenger.dashboard.name}")

            if not current_bot_managers:
                self.stdout.write("No new bots could be initialized")
                return
                
            self.stdout.write("\nTelegram bots are running in background.")
            
        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            time.sleep(10)  # Wait before retrying DB operations
        except Exception as e:
            logger.error(f"Unexpected error in bot initialization: {str(e)}", exc_info=True)

    def shutdown_bots(self):
        """Shutdown all running bots gracefully"""
        if not self.bot_managers:
            return
            
        self.stdout.write("Shutting down all bots...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for manager in self.bot_managers:
            try:
                loop.run_until_complete(manager.shutdown())
                self.stdout.write(f"✓ Bot for {manager.messenger.dashboard.name} shutdown")
            except Exception as e:
                logger.error(f"Error shutting down bot: {str(e)}")
                
        self.bot_managers = []
        loop.close()