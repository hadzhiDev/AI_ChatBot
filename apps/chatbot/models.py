from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

MESSENGER_TYPES = (
    ('instagram', 'Instagram'),
    ('telegram', 'Telegram'),
    ('whatsapp', 'Whatsapp'),
)


class Dashboard(models.Model):
    """
    Represents a user dashboard that can contain multiple AI Assistants
    """
    name = models.CharField(max_length=200, help_text="Name of the dashboard")
    description = models.TextField(blank=True, null=True, help_text="Description of the dashboard's purpose")
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='dashboards',
        help_text="User who owns this dashboard",
        blank=True
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether the dashboard is active")
    theme = models.CharField(
        max_length=50,
        default='light',
        choices=[('light', 'Light'), ('dark', 'Dark'), ('custom', 'Custom')],
        help_text="Visual theme of the dashboard"
    )
    share_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Token for sharing the dashboard"
    )
    is_shared = models.BooleanField(default=False, help_text="Whether the dashboard is shared with others")
    
    class Meta:
        ordering = ['-created_date']
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
    
    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"


class AIAssistant(models.Model):
    """
    Represents an AI Assistant created through ChatGPT premium
    """
    ASSISTANT_TYPES = [
        ('general', 'General Assistant'),
        ('coding', 'Coding Assistant'),
        ('writing', 'Writing Assistant'),
        ('analysis', 'Data Analysis'),
        ('custom', 'Custom Assistant'),
    ]
    
    assistant_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID from the ChatGPT API"
    )
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='assistants',
        help_text="Dashboard this assistant belongs to"
    )
    description = models.TextField(blank=True, null=True, help_text="Purpose and capabilities of the assistant")
    assistant_type = models.CharField(
        max_length=20,
        choices=ASSISTANT_TYPES,
        default='general',
        help_text="Type of assistant"
    )
    created_date = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True, help_text="Last time this assistant was used")
    is_active = models.BooleanField(default=True, help_text="Whether the assistant is active")
    config = models.JSONField(default=dict, help_text="Configuration settings for the assistant", blank=True)
    instructions = models.TextField(default='You are our AI Assistant', help_text="Custom instructions for the assistant")
    model = models.CharField(
        max_length=50,
        default='gpt-4-turbo',
        help_text="Underlying model used by the assistant"
    )
    
    class Meta:
        verbose_name = "AI Assistant"
        verbose_name_plural = "AI Assistants"
    
    def __str__(self):
        return f"{self.model} ({self.get_assistant_type_display()}) - Dashboard: {self.dashboard.name}"


class Messenger(models.Model):
    token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='messangers')
    messenger_type = models.CharField(max_length=100, choices=MESSENGER_TYPES)
    id_instance = models.CharField(max_length=100, null=True, blank=True,
                                   help_text='Not necessary if messanger type is Instagram or Telegram')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dashboard', 'messenger_type'],
                name='unique_dashboard_messenger_type'
            ),
            models.UniqueConstraint(
                fields=['messenger_type', 'token'],
                name='unique_messenger_type_token'
            ),
        ]

    def clean(self):
        super().clean()
        if self.messenger_type == 'whatsapp' and not self.id_instance:
            raise ValidationError({
                'id_instance': _('This field cannot be empty when messanger type is WhatsApp.')
            })

    def __str__(self):
        return f"{self.dashboard} - Active: {self.is_active}"
    

class Message(models.Model): 
    class Meta:
        ordering = ('created_date',)

    text = models.TextField(max_length=500)
    sender_info = models.JSONField(null=True, blank=True)
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    ai_assistant = models.ForeignKey('AIAssistant', on_delete=models.SET_NULL, related_name='messages', null=True,blank=True)
    chat = models.ForeignKey('Chat', models.CASCADE, related_name='messages', null=True, blank=True)
    is_opened = models.BooleanField(default=False)
    outgoing = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now=True)
    media_url = models.URLField(blank=True, null=True)
    media_type = models.CharField(
        max_length=20,
        choices=[('photo', 'Photo'), ('audio', 'Audio'), ('voice', 'Voice')],
        blank=True, null=True
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.chat:
            self.chat.updated_date = now()
            self.chat.save(update_fields=['updated_date'])

 
class Chat(models.Model): 
    class Meta: 
        ordering = ('-created_date', '-updated_date',)
        unique_together = ('messenger', 'client')

    messenger = models.ForeignKey(Messenger, models.SET_NULL, related_name='chats', null=True, blank=True)
    type = models.CharField(max_length=100, choices=MESSENGER_TYPES)
    client = models.OneToOneField('Client', on_delete=models.CASCADE, related_name='chat', null=True)
    whatsapp_chat_id = models.BigIntegerField(null=True, blank=True)
    whatsapp_chat_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='chats', null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    last_updated = models.DateTimeField(auto_now=True)
    assistant = models.ForeignKey(AIAssistant, on_delete=models.SET_NULL, related_name='chats', null=True, blank=True)

    def __str__(self):
        return f'{self.id} - {self.type}'


class Client(models.Model):
    # class Meta:
    #     ordering = ('-created_date', '-updated_date')

    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    whatsapp_chat_id = models.CharField(max_length=100, null=True, blank=True)
    messenger_type = models.CharField(max_length=100, choices=MESSENGER_TYPES)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=200, null=True, blank=True)
    username = models.CharField(max_length=200, null=True, blank=True)
    is_bot = models.BooleanField(default=False)

    def __str__(self):
        return f'@{self.username} - {self.name}'