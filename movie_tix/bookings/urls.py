from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('movie/<int:movie_id>/select-date-time/', views.select_date_time, name='select_date_time'),
    path('select-seats/<int:showtime_id>/', views.select_seats, name='select_seats'),
    path('payment/', views.payment, name='payment'),
    path('payment-confirm/<int:booking_id>/', views.payment_confirm, name='payment_confirm'),
    path('booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<int:booking_id>/download-ticket/', views.download_ticket, name='download_ticket'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('confirm-booking/', views.confirm_booking, name='confirm_booking'),
]
