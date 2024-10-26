from django.contrib import admin
from queue_manager.models import Queue, UserProfile, Participant


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'status', 'is_closed', 'estimated_wait_time', 'created_at')
    search_fields = ('name', 'created_by__username')
    list_filter = ('status', 'is_closed', 'created_at')
    ordering = ('-created_at',)
    readonly_field = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'created_by', 'is_closed', 'status')
        }),
        ('Advanced options', {
            'classes': ('collapse',),
            'fields': ('estimated_wait_time',),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'phone_no')
    search_fields = ('user__username', 'user_type')
    list_filter = ('user_type',)
    ordering = ('user',)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'queue', 'position', 'joined_at')
    search_fields = ('user__username', 'queue__name')
    list_filter = ('queue', 'joined_at')
    ordering = ('-joined_at',)
    readonly_fields = ('joined_at',)
