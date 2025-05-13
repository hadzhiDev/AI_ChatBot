import logging
import openai
import asyncio
import requests
from asgiref.sync import sync_to_async
import io
from pydub import AudioSegment
from datetime import datetime
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
)
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.chatbot.models import Messenger, Message, Chat, Client, AIAssistant, Dashboard


logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)

openai.api_key = settings.OPENAI_API_KEY

class TelegramBotManager:
    def __init__(self, messenger_instance):
        self.messenger = messenger_instance
        self.token = messenger_instance.token
        self.dashboard = messenger_instance.dashboard
        self.application = None
        self.updater = None
        self.active_chats = set()
        logger.info(f"Initializing TelegramBotManager for dashboard: {self.dashboard.name}")

    
    def register_handlers(self):
        """Register all command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.ALL, self.handle_other_messages))

    async def start_polling(self):
        """Start polling for updates"""
        try:
            await self.application.updater.start_polling()
            logger.info("Polling started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start polling: {str(e)}")
            return False

    async def initialize(self):
        """Initialize the Telegram bot application"""
        try:
            logger.info(f"Attempting to initialize bot with token (first 5 chars): {self.token[:5]}...")
            
            # Create application with updater for polling
            self.application = Application.builder().token(self.token).build()
            self.updater = self.application.updater
            
            # Register handlers first
            self.register_handlers()
            logger.info("Handlers registered successfully")
            
            # Initialize and start
            await self.application.initialize()
            await self.application.start()
            
            # Start polling explicitly
            await self.updater.start_polling()
            logger.info("Polling started successfully")
            
            self.bot = self.application.bot
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username} (ID: {bot_info.id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {str(e)}", exc_info=True)
            return False

    async def shutdown(self):
        """Shutdown the bot gracefully"""
        if self.application:
            try:
                logger.info("Starting shutdown process")
                await self.application.stop()
                await self.application.shutdown()
                logger.info(f"Successfully shutdown Telegram bot for dashboard {self.dashboard.name}")
            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}", exc_info=True)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            logger.info(f"Received /start from user {user.id} in chat {chat.id}")
            
            # Get or create client
            client = await self.get_or_create_client(user, chat)
            logger.info(f"Client {'created' if client._state.adding else 'retrieved'}: {client.id}")
            
            # Get or create chat
            telegram_chat = await self.get_or_create_chat(chat, client)
            logger.info(f"Chat {'created' if telegram_chat._state.adding else 'retrieved'}: {telegram_chat.id}")
            
            # Get the default AI assistant
            assistant = await self.get_default_assistant()
            logger.info(f"Assistant retrieved: {assistant.id if assistant else 'None'}")
            
            welcome_message = f"👋 Hello {user.first_name}! I'm your AI assistant."
            if assistant:
                welcome_message += f"\n\nCurrent assistant: {assistant.get_assistant_type_display()}"
            
            await context.bot.send_message(chat_id=chat.id, text=welcome_message)
            logger.info(f"Sent welcome message to chat {chat.id}")
            
            self.active_chats.add(chat.id)
            logger.info(f"Added chat {chat.id} to active sessions")
            
        except Exception as e:
            logger.error(f"Error in start_command: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ An error occurred. Please try again later."
            )

    async def handle_message(self, update: Update, context: CallbackContext):
        """Handle incoming text messages"""
        try:
            logger.info(f"Raw update: {update.to_dict()}")
            user = update.effective_user
            chat = update.effective_chat
            message_text = update.message.text
            logger.info(f"Received message from {user.id} in chat {chat.id}: {message_text[:50]}...")
            
            if chat.id not in self.active_chats:
                logger.warning(f"Chat {chat.id} not in active sessions")
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="Please start a new session with /start"
                )
                return
            
            # Get or create client and chat
            client = await self.get_or_create_client(user, chat)
            telegram_chat = await self.get_or_create_chat(chat, client)
            logger.info(f"Client/Chat ready - Client ID: {client.id}, Chat ID: {telegram_chat.id}")
            
            # Create incoming message record
            incoming_message = await sync_to_async(Message.objects.create)(
                text=message_text,
                client=client,
                chat=telegram_chat,
                is_opened=True,
                outgoing=False,
                sender_info={
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username,
                    'id': user.id
                }
            )
            logger.info(f"Created incoming message record: {incoming_message.id}")
            
            # Get AI assistant
            assistant = await self.get_default_assistant()
            if not assistant:
                logger.warning("No active assistant found for dashboard")
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="⚠️ No active AI assistant is configured for this dashboard."
                )
                return
            
            # Get conversation history
            history = await self.get_conversation_history(telegram_chat)
            logger.info(f"Retrieved {len(history)} history messages")
            
            # Process with AI
            response_text = await self.process_with_assistant(
                assistant, 
                message_text, 
                client,
                history
            )
            logger.info("Generated AI response")
            
            # Send response
            await context.bot.send_message(chat_id=chat.id, text=response_text)
            logger.info("Sent response to user")
            
            # Create outgoing message record
            outgoing_message = await sync_to_async(Message.objects.create)(
                text=response_text,
                client=client,
                ai_assistant=assistant,
                chat=telegram_chat,
                is_opened=True,
                outgoing=True,
                sender_info={
                    'assistant_id': assistant.assistant_id,
                    'assistant_type': assistant.assistant_type,
                    'model': assistant.model
                }
            )
            logger.info(f"Created outgoing message record: {outgoing_message.id}")
            
        except Exception as e:
            logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ An error occurred while processing your message. Please try again."
            )

    async def handle_other_messages(self, update: Update, context: CallbackContext):
        """Handle non-text messages (photos, audio, etc.)"""
        try:
            chat = update.effective_chat
            message = update.message
            
            if message.photo:
                await self.handle_photo(chat, message, context)
            elif message.audio or message.voice:
                await self.handle_audio(chat, message, context)
            else:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="I currently support text, photos and audio messages."
                )
                
        except Exception as e:
            logger.error(f"Error in handle_other_messages: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ An error occurred while processing your message."
            )

    async def handle_photo(self, chat, message, context):
        """Process photo messages"""
        try:
            # Get the highest quality photo
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_url = file.file_path
            
            logger.info(f"Received photo from chat {chat.id}, file URL: {file_url}")
            
            # Get or create client and chat
            client = await self.get_or_create_client(message.from_user, chat)
            telegram_chat = await self.get_or_create_chat(chat, client)
            
            # Check if assistant supports images
            assistant = await self.get_default_assistant()
            if not assistant:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="⚠️ No active AI assistant is configured."
                )
                return
                
            if not self.model_supports_images(assistant.model):
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="I can't process images with my current configuration."
                )
                return
                
            # Process with OpenAI
            response = await self.process_with_assistant(
                assistant=assistant,
                message_text="Describe this image",
                client=client,
                image_url=file_url
            )
            
            await context.bot.send_message(chat_id=chat.id, text=response)
            
        except Exception as e:
            logger.error(f"Error processing photo: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ Failed to process your image."
            )

    

    async def transcribe_audio(self, audio_url):
        """Transcribe audio using OpenAI Whisper API"""
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Download audio file
            with requests.Session() as session:
                audio_response = await sync_to_async(session.get)(audio_url, stream=True)
                audio_response.raise_for_status()
                
                # Convert to file-like object
                audio_file = io.BytesIO(audio_response.content)
                
                # Convert to MP3 if needed (Whisper prefers specific formats)
                try:
                    audio = AudioSegment.from_file(audio_file)
                    audio_file = io.BytesIO()
                    audio.export(audio_file, format="mp3")
                    audio_file.seek(0)
                except Exception as e:
                    logger.warning(f"Audio conversion warning: {str(e)}")
                    audio_file.seek(0)
                
                # Prepare file for Whisper API
                audio_file.name = "audio.mp3"  # Required by OpenAI API
                
                transcription = await asyncio.to_thread(
                    client.audio.transcriptions.create,
                    file=audio_file,
                    model="whisper-1",
                    response_format="text"
                )
                return transcription
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Audio download failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return None

    async def handle_audio(self, chat, message, context):
        """Process audio messages with proper error handling"""
        try:
            audio = message.audio or message.voice
            file = await context.bot.get_file(audio.file_id)
            file_url = file.file_path
            
            logger.info(f"Processing audio from chat {chat.id}")
            
            # Get or create client
            client = await self.get_or_create_client(message.from_user, chat)
            assistant = await self.get_default_assistant()
            
            if not assistant:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="⚠️ No active AI assistant is configured."
                )
                return

            # Show "processing" message
            processing_msg = await context.bot.send_message(
                chat_id=chat.id,
                text="🔊 Processing your audio message..."
            )

            # Transcribe audio
            transcription = await self.transcribe_audio(file_url)
            
            if not transcription:
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=processing_msg.message_id,
                    text="⚠️ Failed to transcribe audio. Please try again."
                )
                return

            logger.info(f"Transcription result: {transcription[:100]}...")
            
            # Process with assistant
            response = await self.process_with_assistant(
                assistant=assistant,
                message_text=transcription,
                client=client
            )
            
            # Update message with result
            await context.bot.edit_message_text(
                chat_id=chat.id,
                message_id=processing_msg.message_id,
                text=response
            )
            
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ Failed to process your audio message. Please try again later."
            )
            

    def model_supports_images(self, model_name):
        """Check if the model supports image processing"""
        image_supporting_models = [
            'gpt-4-turbo',
            'gpt-4-vision-preview',
            'gpt-4o'
        ]
        return any(model in model_name.lower() for model in image_supporting_models)

    async def get_or_create_client(self, user, chat):
        """Get or create a Client record"""
        try:
            client = await sync_to_async(Client.objects.get)(
                dashboard=self.dashboard,
                telegram_chat_id=user.id
            )
            logger.debug(f"Found existing client: {client.id}")
        except Client.DoesNotExist:
            client = await sync_to_async(Client.objects.create)(
                dashboard=self.dashboard,
                telegram_chat_id=user.id,
                name=f"{user.first_name} {user.last_name}" if user.last_name else user.first_name,
                username=user.username,
                is_bot=user.is_bot
            )
            logger.info(f"Created new client: {client.id}")
        except Exception as e:
            logger.error(f"Error in get_or_create_client: {str(e)}", exc_info=True)
            raise
        return client

    async def get_or_create_chat(self, chat, client):
        """Get or create a Chat record"""
        try:
            telegram_chat = await sync_to_async(Chat.objects.get)(
                messenger=self.messenger,
                client=client
            )
            logger.debug(f"Found existing chat: {telegram_chat.id}")
        except Chat.DoesNotExist:
            telegram_chat = await sync_to_async(Chat.objects.create)(
                messenger=self.messenger,
                type='telegram',
                client=client,
                is_active=True,
                dashboard=self.dashboard
            )
            logger.info(f"Created new chat: {telegram_chat.id}")
        except Exception as e:
            logger.error(f"Error in get_or_create_chat: {str(e)}", exc_info=True)
            raise
        return telegram_chat

    async def get_default_assistant(self):
        """Get the default AI assistant for this dashboard"""
        try:
            assistant = await sync_to_async(AIAssistant.objects.filter(
                dashboard=self.dashboard,
                is_active=True
            ).order_by('-created_date').first)()
            if assistant:
                logger.debug(f"Found assistant: {assistant.id} ({assistant.assistant_type})")
            else:
                logger.warning("No active assistant found for dashboard")
            return assistant
        except Exception as e:
            logger.error(f"Error getting default assistant: {str(e)}", exc_info=True)
            return None

    async def get_conversation_history(self, chat, limit=5):
        """Get recent conversation history for context"""
        try:
            messages = await sync_to_async(list)(
                Message.objects.filter(chat=chat)
                .order_by('-created_date')[:limit]
            )
            history = [
                {
                    'role': 'assistant' if msg.outgoing else 'user',
                    'content': msg.text,
                    'timestamp': msg.created_date.isoformat()
                }
                for msg in reversed(messages)
            ]
            logger.debug(f"Retrieved {len(history)} history messages")
            return history
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}", exc_info=True)
            return []
    
    async def process_with_assistant(self, assistant, message_text, client, history=None, image_url=None):
        """Process the message with the OpenAI API (now supports images)"""
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            messages = []
            
            # System message
            if assistant.instructions:
                messages.append({'role': 'system', 'content': assistant.instructions})
            
            # Conversation history
            if history:
                messages.extend(history)
            
            # Build content array
            content = [{'type': 'text', 'text': message_text}]
            
            if image_url:
                content.append({
                    'type': 'image_url',
                    'image_url': {'url': image_url}
                })
            
            messages.append({
                'role': 'user',
                'content': content
            })
            
            logger.info(f"Calling OpenAI with model: {assistant.model}")
            
            # Make the API call
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=assistant.model,
                messages=messages,
                temperature=assistant.config.get('temperature', 0.7),
                max_tokens=assistant.config.get('max_tokens', 1000),
            )
            
            return response.choices[0].message.content
            
        except AuthenticationError as e:
            logger.error("OpenAI Authentication Failed. Check your API key.")
            return "⚠️ Bot configuration error. Please contact support."
            
        except RateLimitError as e:
            logger.error("OpenAI Rate Limit Exceeded")
            return "⏳ I'm getting too many requests. Please try again later."
            
        except APIConnectionError as e:
            logger.error("OpenAI Connection Error")
            return "🔌 Connection error. Please try again."
            
        except Exception as e:
            logger.error(f"OpenAI Processing Error: {str(e)}", exc_info=True)
            return "⚠️ I encountered an error processing your request. Please try again."
            