from django.contrib import admin
from .models import Theater, Showtime, Seat, Booking

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'total_seats')
    search_fields = ('name', 'location')

@admin.register(Showtime)
class ShowtimeAdmin(admin.ModelAdmin):
    list_display = ('movie', 'theater', 'date', 'time', 'price', 'get_available_seats')
    list_filter = ('date', 'theater')
    search_fields = ('movie__title',)
    date_hierarchy = 'date'

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('row', 'number')
    list_filter = ('row',)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'showtime', 'get_seats_display', 'total_price', 'status', 'booking_time')
    list_filter = ('status', 'booking_time', 'showtime__date')
    search_fields = ('user__username', 'showtime__movie__title')
    readonly_fields = ('booking_time', 'booking_reference')
