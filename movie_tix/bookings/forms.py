from django import forms
from .models import Booking, Seat

class PaymentForm(forms.Form):
    PAYMENT_METHODS = [
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
    ]

    MONTH_CHOICES = [(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)]
    
    current_year = 2025  # Updated for your project's date
    YEAR_CHOICES = [(str(i)[-2:], str(i)) for i in range(current_year, current_year + 11)]

    # Payment method selection
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        widget=forms.RadioSelect(attrs={'class': 'payment-method-radio'}),
        required=True
    )

    # Billing Information
    full_name = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Full Name',
            'class': 'form-control billing-field',
            'autocomplete': 'name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email Address',
            'class': 'form-control billing-field',
            'autocomplete': 'email'
        })
    )
    
    phone = forms.CharField(
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Phone Number',
            'class': 'form-control billing-field',
            'autocomplete': 'tel'
        })
    )
    
    address_line1 = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Address Line 1',
            'class': 'form-control billing-field',
            'autocomplete': 'address-line1'
        })
    )
    
    address_line2 = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Address Line 2 (Optional)',
            'class': 'form-control billing-field',
            'autocomplete': 'address-line2'
        })
    )
    
    city = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'City',
            'class': 'form-control billing-field',
            'autocomplete': 'address-level2'
        })
    )
    
    state = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'State/Province',
            'class': 'form-control billing-field',
            'autocomplete': 'address-level1'
        })
    )
    
    zip_code = forms.CharField(
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'ZIP/Postal Code',
            'class': 'form-control billing-field',
            'autocomplete': 'postal-code'
        })
    )
    
    country = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Country',
            'class': 'form-control billing-field',
            'autocomplete': 'country-name'
        })
    )

    # Student discount option
    apply_student_discount = forms.BooleanField(
        required=False,
        label='Apply Student Discount',
        help_text='Student ID verification required at the theater'
    )
    
    student_id = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Your student ID number',
            'class': 'form-control',
            'autocomplete': 'off'
        })
    )

    # Card details
    card_number = forms.CharField(
        required=False,
        max_length=19,  # 16 digits + 3 spaces
        widget=forms.TextInput(attrs={
            'placeholder': '•••• •••• •••• ••••',
            'class': 'form-control card-number-input',
            'autocomplete': 'cc-number',
            'id': 'card-number'
        })
    )
    
    card_holder = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Name on Card',
            'class': 'form-control',
            'autocomplete': 'cc-name',
            'id': 'card-holder'
        })
    )
    
    # Split expiry into month and year for better UX
    expiry_month = forms.ChoiceField(
        required=False,
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control expiry-select',
            'autocomplete': 'cc-exp-month',
            'id': 'expiry-month'
        })
    )
    
    expiry_year = forms.ChoiceField(
        required=False,
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control expiry-select',
            'autocomplete': 'cc-exp-year',
            'id': 'expiry-year'
        })
    )
    
    cvv = forms.CharField(
        required=False,
        max_length=4,
        widget=forms.PasswordInput(attrs={
            'placeholder': '•••',
            'class': 'form-control cvv-input',
            'autocomplete': 'cc-csc',
            'id': 'card-cvv'
        })
    )
    
    # Terms and conditions
    agree_to_terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms and Conditions'
    )
    
    # Stripe token field (hidden)
    stripe_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        apply_student_discount = cleaned_data.get('apply_student_discount')

        # Validate required billing information
        required_billing_fields = ['full_name', 'email', 'phone', 'address_line1', 'city', 'state', 'zip_code', 'country']
        for field in required_billing_fields:
            if not cleaned_data.get(field):
                self.add_error(field, f'{field.replace("_", " ").title()} is required')

        # Validate email format
        email = cleaned_data.get('email', '')
        if email and '@' not in email:
            self.add_error('email', 'Enter a valid email address')

        # Validate student discount
        if apply_student_discount and not cleaned_data.get('student_id'):
            self.add_error('student_id', 'Student ID is required when applying student discount')

        # Validate credit card details
        if payment_method == 'card':
            # If using Stripe token, we don't need to validate the card fields directly
            if not cleaned_data.get('stripe_token'):
                if not cleaned_data.get('card_number'):
                    self.add_error('card_number', 'Card number is required')
                if not cleaned_data.get('card_holder'):
                    self.add_error('card_holder', 'Name on card is required')
                if not cleaned_data.get('expiry_month'):
                    self.add_error('expiry_month', 'Expiration month is required')
                if not cleaned_data.get('expiry_year'):
                    self.add_error('expiry_year', 'Expiration year is required')
                if not cleaned_data.get('cvv'):
                    self.add_error('cvv', 'Security code is required')
                
                # Basic card validation
                card_number = cleaned_data.get('card_number', '').replace(' ', '')
                if card_number:
                    if not card_number.isdigit():
                        self.add_error('card_number', 'Card number should contain only digits')
                    if not (13 <= len(card_number) <= 19):
                        self.add_error('card_number', 'Card number should be between 13 and 19 digits')
                    
                    # Basic Luhn algorithm check (card checksum)
                    # This is just a basic implementation, a more robust one would be used in production
                    if not self._is_valid_luhn(card_number):
                        self.add_error('card_number', 'Invalid card number')
                
                # CVV validation
                cvv = cleaned_data.get('cvv', '')
                if cvv and not (cvv.isdigit() and 3 <= len(cvv) <= 4):
                    self.add_error('cvv', 'CVV should be 3 or 4 digits')

        # For non-card payment methods, we would add specific validations here
        elif payment_method == 'paypal':
            # PayPal specific validation would go here
            pass
        elif payment_method in ['apple_pay', 'google_pay']:
            # Digital wallet specific validation would go here
            pass

        return cleaned_data
        
    def _is_valid_luhn(self, card_number):
        """
        Check if the card number passes the Luhn algorithm
        This is a simplified version for validation purposes
        """
        digits = [int(d) for d in card_number]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        total = sum(odd_digits)
        for digit in even_digits:
            total += sum(divmod(digit * 2, 10))
        return total % 10 == 0

class BookingForm(forms.Form):
    """Form for creating a new booking with student discount option"""
    apply_student_discount = forms.BooleanField(
        required=False,
        label='Apply Student Discount',
        help_text='Student ID verification required at the theater'
    )
    
    student_id = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Your student ID number'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        apply_student_discount = cleaned_data.get('apply_student_discount')
        
        if apply_student_discount and not cleaned_data.get('student_id'):
            self.add_error('student_id', 'Student ID is required when applying student discount')
            
        return cleaned_data
