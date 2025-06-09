from django.contrib import admin
from .models import Event, Category, EventImage, TicketType, Booking, Review

# Register your models here.

class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 1

class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1

class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'start_date', 'is_published')
    list_filter = ('is_published', 'event_type', 'category')
    search_fields = ('title', 'description', 'location')
    inlines = [EventImageInline, TicketTypeInline]

admin.site.register(Event, EventAdmin)
admin.site.register(Category)
admin.site.register(Booking)
admin.site.register(Review)