import logging
import asyncio
import time
from asgiref.sync import sync_to_async
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
        
        # Create and run the main async loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the main async function
            loop.run_until_complete(self.async_main())
        except KeyboardInterrupt:
            self.stdout.write("\nReceived shutdown signal...")
        finally:
            self.shutdown_bots()
            loop.close()
            self.stdout.write("Telegram bot manager stopped.")

    async def async_main(self):
        """Main async loop"""
        while not self.shutdown_flag:
            try:
                # Get active messengers
                messengers = await sync_to_async(list)(
                    Messenger.objects.filter(
                        messenger_type='telegram',
                        is_active=True
                    ).select_related('dashboard')
                )
                
                if not messengers:
                    self.stdout.write("No active Telegram messengers found.")
                    await asyncio.sleep(60)
                    continue
                    
                self.stdout.write(f"Found {len(messengers)} active Telegram messenger(s)")
                
                # Initialize all bots
                current_bot_managers = []
                for messenger in messengers:
                    if any(m.messenger.id == messenger.id for m in self.bot_managers):
                        continue
                        
                    manager = TelegramBotManager(messenger)
                    if await manager.initialize():  # Changed to direct await
                        current_bot_managers.append(manager)
                        self.bot_managers.append(manager)
                        self.stdout.write(f"✓ Bot for {messenger.dashboard.name} initialized")
                    
                if not current_bot_managers:
                    self.stdout.write("No new bots could be initialized")
                    await asyncio.sleep(60)
                    continue
                    
                # Keep running while bots are active
                while not self.shutdown_flag and self.bot_managers:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in bot manager: {str(e)}", exc_info=True)
                await asyncio.sleep(30)

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