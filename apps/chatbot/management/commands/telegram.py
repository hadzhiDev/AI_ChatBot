import logging
import asyncio
import sys
from django.core.management.base import BaseCommand
from django.db import DatabaseError
from apps.chatbot.management.telegram_manager import TelegramBotManager
from apps.chatbot.models import Messenger

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Runs all Telegram bots configured in the system'

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
            
            # Create event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Initialize all bots
            bot_managers = []
            for messenger in messengers:
                manager = TelegramBotManager(messenger)
                if loop.run_until_complete(manager.initialize()):
                    bot_managers.append(manager)
                    self.stdout.write(f"✓ Bot for {messenger.dashboard.name} initialized")
                else:
                    self.stdout.write(f"× Failed to initialize bot for {messenger.dashboard.name}")

            if not bot_managers:
                self.stdout.write("No bots could be initialized")
                return
                
            self.stdout.write("\nAll Telegram bots are running. Press Ctrl+C to stop.")
            
            # Keep the application running
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                self.stdout.write("\nShutting down bots...")
                for manager in bot_managers:
                    loop.run_until_complete(manager.shutdown())
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Critical error: {str(e)}", exc_info=True)
            self.stdout.write(f"Error: {str(e)}")
        finally:
            self.stdout.write("Telegram bot manager stopped.")
