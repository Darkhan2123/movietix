from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from movies.models import Movie
import uuid


class Theater(models.Model):
    """Represents a movie theater"""
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Theater features
    total_seats = models.PositiveIntegerField(default=48)  # Default: 6 rows × 8 seats
    has_imax = models.BooleanField(default=False)
    has_3d = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    is_accessible = models.BooleanField(default=True)

    # Contact info
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Operating hours
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    # Staff
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_theaters'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_full_address(self):
        return ", ".join(part for part in [self.address, self.city, self.state, self.postal_code] if part)

    def get_available_features(self):
        return [
            feature for condition, feature in [
                (self.has_imax, "IMAX"),
                (self.has_3d, "3D"),
                (self.has_parking, "Parking"),
                (self.is_accessible, "Wheelchair Accessible")
            ] if condition
        ]


class Showtime(models.Model):
    """Represents a scheduled movie showing"""
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='showtimes')
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='showtimes')
    date = models.DateField()
    time = models.TimeField()
    price = models.DecimalField(max_digits=6, decimal_places=2, default=10.00)
    student_price = models.DecimalField(max_digits=6, decimal_places=2, default=8.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['theater', 'date', 'time']
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.movie.title} - {self.date} {self.time}"

    def get_available_seats(self):
        """Returns the number of available (unbooked) seats"""
        with transaction.atomic():
            showtime = Showtime.objects.select_for_update().get(pk=self.pk)
            booked = Seat.objects.filter(
                bookings__showtime=showtime,
                bookings__status='confirmed'
            ).distinct().count()
            return self.theater.total_seats - booked

    def is_full(self):
        return self.get_available_seats() <= 0

    def is_almost_full(self):
        available = self.get_available_seats()
        return (available / self.theater.total_seats) < 0.2


class Seat(models.Model):
    """Represents an individual seat"""
    ROW_CHOICES = [(chr(i), chr(i)) for i in range(ord('A'), ord('G'))]  # A–F

    row = models.CharField(max_length=1, choices=ROW_CHOICES)
    number = models.PositiveIntegerField()

    class Meta:
        unique_together = ['row', 'number']
        ordering = ['row', 'number']

    def __str__(self):
        return f"{self.row}{self.number}"

    def clean(self):
        if not (1 <= self.number <= 8):
            raise ValidationError({'number': 'Seat number must be between 1 and 8.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Booking(models.Model):
    """Represents a booking made by a user"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    showtime = models.ForeignKey(Showtime, on_delete=models.CASCADE, related_name='bookings')
    seats = models.ManyToManyField(Seat, related_name='bookings')

    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    booking_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=20, blank=True, null=True)

    # Discount info
    student_discount_applied = models.BooleanField(default=False)
    student_discount_verified = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-booking_time']

    def __str__(self):
        return f"Booking {self.booking_reference} by {self.user.username}"

    def get_seats_display(self):
        return ", ".join(str(seat) for seat in self.seats.all().order_by('row', 'number'))

    def get_seat_count(self):
        return self.seats.count()

    def calculate_total_price(self):
        price = self.showtime.student_price if self.student_discount_applied else self.showtime.price
        return self.get_seat_count() * price

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.calculate_total_price()
        super().save(*args, **kwargs)
