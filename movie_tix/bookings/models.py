from django.db import models
from django.contrib.auth.models import User
from movies.models import Movie
import uuid

class Theater(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    total_seats = models.IntegerField(default=48)  # Default 6 rows x 8 seats
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Theater details
    description = models.TextField(blank=True)
    has_imax = models.BooleanField(default=False)
    has_3d = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    is_accessible = models.BooleanField(default=True)
    
    # Operating hours
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    
    # Manager - relationship to user
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_theaters')

    def __str__(self):
        return self.name
        
    def get_full_address(self):
        """Return the full formatted address"""
        parts = [self.address, self.city, self.state, self.postal_code]
        return ", ".join(part for part in parts if part)
        
    def get_available_features(self):
        """Return a list of available features"""
        features = []
        if self.has_imax:
            features.append("IMAX")
        if self.has_3d:
            features.append("3D")
        if self.has_parking:
            features.append("Parking")
        if self.is_accessible:
            features.append("Wheelchair Accessible")
        return features

class Showtime(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='showtimes')
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='showtimes')
    date = models.DateField()
    time = models.TimeField()
    price = models.DecimalField(max_digits=6, decimal_places=2, default=10.00)
    student_price = models.DecimalField(max_digits=6, decimal_places=2, default=8.00)  # Student discounted price
    is_active = models.BooleanField(default=True)  # To enable/disable specific showtimes

    class Meta:
        unique_together = ['theater', 'date', 'time']
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.movie.title} - {self.date} {self.time}"

    def get_available_seats(self):
        from django.db import transaction
        
        # Use a transaction with select_for_update to prevent race conditions
        with transaction.atomic():
            # Lock this showtime row 
            showtime = type(self).objects.select_for_update().get(id=self.id)
            
            # Count booked seats with a JOIN to ensure atomicity
            booked_seats = Seat.objects.filter(
                bookings__showtime=showtime,
                bookings__status='confirmed'
            ).distinct().count()
            
            return showtime.theater.total_seats - booked_seats
        
    def is_full(self):
        return self.get_available_seats() <= 0
        
    def is_almost_full(self):
        # Return true if less than 20% of seats are available
        available_percent = (self.get_available_seats() / self.theater.total_seats) * 100
        return available_percent < 20

class Seat(models.Model):
    ROW_CHOICES = [
        ('A', 'A'), ('B', 'B'), ('C', 'C'),
        ('D', 'D'), ('E', 'E'), ('F', 'F'),
    ]

    row = models.CharField(max_length=1, choices=ROW_CHOICES)
    number = models.IntegerField()  # 1-8 for each row
    
    class Meta:
        unique_together = ['row', 'number']
        ordering = ['row', 'number']

    def __str__(self):
        return f"{self.row}{self.number}"
        
    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate seat number is within range (1-8)
        if self.number < 1 or self.number > 8:
            raise ValidationError({'number': f'Seat number must be between 1 and 8, got {self.number}'})
    
    def save(self, *args, **kwargs):
        # Run validation before saving
        self.clean()
        super().save(*args, **kwargs)

class Booking(models.Model):
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
    booking_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Student discount fields
    student_discount_applied = models.BooleanField(default=False)
    student_discount_verified = models.BooleanField(default=False)
    
    # Payment method tracking
    payment_method = models.CharField(max_length=20, blank=True, null=True)
    
    # Notes (for staff, verification, etc.)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Booking {self.booking_reference} - {self.user.username}"

    def get_seats_display(self):
        return ", ".join(str(seat) for seat in self.seats.all().order_by('row', 'number'))
        
    def get_seat_count(self):
        return self.seats.count()
        
    def calculate_total_price(self):
        """Calculate total price based on seats and whether student discount is applied"""
        seat_count = self.get_seat_count()
        
        if self.student_discount_applied:
            return seat_count * self.showtime.student_price
        else:
            return seat_count * self.showtime.price
            
    def save(self, *args, **kwargs):
        """Override save to ensure total price is calculated if not provided"""
        if not self.total_price:
            self.total_price = self.calculate_total_price()
        super().save(*args, **kwargs)
