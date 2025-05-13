from django.contrib import admin
from django.utils.html import format_html
from .models import Dashboard, AIAssistant, Messenger, Message, Chat, Client

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'is_shared', 'theme', 'created_date')
    list_filter = ('is_active', 'is_shared', 'theme', 'created_date')
    search_fields = ('name', 'owner__username', 'description')
    readonly_fields = ('created_date', 'updated_date', 'share_token')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'owner', 'is_active')
        }),
        ('Display Settings', {
            'fields': ('theme',)
        }),
        ('Sharing', {
            'fields': ('is_shared', 'share_token')
        }),
        ('Timestamps', {
            'fields': ('created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner')
    
    def get_fieldsets(self, request, obj=None):
        if obj:  # Editing existing object
            return super().get_fieldsets(request, obj)
        # For add form
        return (
            ('Basic Information', {
                'fields': ('name', 'description', 'is_active')
            }),
            ('Display Settings', {
                'fields': ('theme',)
            }),
            ('Sharing', {
                'fields': ('is_shared',)
            }),
        )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(AIAssistant)
class AIAssistantAdmin(admin.ModelAdmin):
    list_display = ('model', 'dashboard', 'assistant_type', 'is_active', 'last_used')
    list_filter = ('model', 'assistant_type', 'is_active', 'dashboard__name')
    search_fields = ('assistant_id', 'description', 'dashboard__name')
    readonly_fields = ('created_date',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('dashboard', 'assistant_type', 'is_active')
        }),
        ('Technical Details', {
            'fields': ('assistant_id', 'model', 'config')
        }),
        ('Behavior', {
            'fields': ('description', 'instructions')
        }),
        ('Usage', {
            'fields': ('last_used', 'created_date'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('dashboard', 'dashboard__owner')


@admin.register(Messenger)
class MessengerAdmin(admin.ModelAdmin):
    list_display = ('messenger_type', 'dashboard', 'is_active', 'token_preview')
    list_filter = ('messenger_type', 'is_active')
    search_fields = ('name', 'token', 'dashboard__name')
    readonly_fields = ('token_preview',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('messenger_type', 'dashboard', 'is_active')
        }),
        ('Authentication', {
            'fields': ('token', 'token_preview', 'id_instance')
        }),
    )
    
    def token_preview(self, obj):
        if obj.token:
            return format_html('<code>{}</code>', obj.token[:15] + '...' if len(obj.token) > 15 else obj.token)
        return "-"
    token_preview.short_description = "Token Preview"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('dashboard', 'dashboard__owner')
    

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('chat', 'timestamp', 'client', 'ai_assistant')
    list_filter = ('timestamp',)
    search_fields = ('chat',)
    readonly_fields = ('timestamp',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('client', 'ai_assistant', 'chat', 'text', 'sender_info')
        }),
        ('Timestamps', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'ai_assistant')
    

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('client', 'assistant', 'created_date', 'last_updated')
    list_filter = ('assistant__model', 'created_date')
    search_fields = ('client__name', 'assistant__description')
    readonly_fields = ('created_date', 'last_updated')
    fieldsets = (
        ('Basic Information', {
            'fields': ('client', 'assistant')
        }),
        ('Timestamps', {
            'fields': ('created_date', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'assistant')
    

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'messenger_type')
    list_filter = ('messenger_type',)
    search_fields = ('name',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'messenger_type')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('messenger_type')