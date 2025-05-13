from django import forms


class StudentDiscountMixin(forms.Form):
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

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('apply_student_discount') and not cleaned_data.get('student_id'):
            self.add_error('student_id', 'Student ID is required when applying student discount')
        return cleaned_data


class PaymentForm(StudentDiscountMixin, forms.Form):
    PAYMENT_METHODS = [
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay'),
    ]
    MONTH_CHOICES = [(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)]
    YEAR_CHOICES = [(str(i)[-2:], str(i)) for i in range(2025, 2036)]

    payment_method = forms.ChoiceField(choices=PAYMENT_METHODS, widget=forms.RadioSelect(attrs={'class': 'payment-method-radio'}))
    full_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Full Name', 'class': 'form-control billing-field', 'autocomplete': 'name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email Address', 'class': 'form-control billing-field', 'autocomplete': 'email'}))
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'placeholder': 'Phone Number', 'class': 'form-control billing-field', 'autocomplete': 'tel'}))
    address_line1 = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Address Line 1', 'class': 'form-control billing-field', 'autocomplete': 'address-line1'}))
    address_line2 = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Address Line 2 (Optional)', 'class': 'form-control billing-field', 'autocomplete': 'address-line2'}))
    city = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'City', 'class': 'form-control billing-field', 'autocomplete': 'address-level2'}))
    state = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'State/Province', 'class': 'form-control billing-field', 'autocomplete': 'address-level1'}))
    zip_code = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'placeholder': 'ZIP/Postal Code', 'class': 'form-control billing-field', 'autocomplete': 'postal-code'}))
    country = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Country', 'class': 'form-control billing-field', 'autocomplete': 'country-name'}))

    card_number = forms.CharField(required=False, max_length=19, widget=forms.TextInput(attrs={'placeholder': '•••• •••• •••• ••••', 'class': 'form-control card-number-input', 'autocomplete': 'cc-number', 'id': 'card-number'}))
    card_holder = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Name on Card', 'class': 'form-control', 'autocomplete': 'cc-name', 'id': 'card-holder'}))
    expiry_month = forms.ChoiceField(required=False, choices=MONTH_CHOICES, widget=forms.Select(attrs={'class': 'form-control expiry-select', 'autocomplete': 'cc-exp-month', 'id': 'expiry-month'}))
    expiry_year = forms.ChoiceField(required=False, choices=YEAR_CHOICES, widget=forms.Select(attrs={'class': 'form-control expiry-select', 'autocomplete': 'cc-exp-year', 'id': 'expiry-year'}))
    cvv = forms.CharField(required=False, max_length=4, widget=forms.PasswordInput(attrs={'placeholder': '•••', 'class': 'form-control cvv-input', 'autocomplete': 'cc-csc', 'id': 'card-cvv'}))

    agree_to_terms = forms.BooleanField(label='I agree to the Terms and Conditions')
    stripe_token = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('payment_method') == 'card' and not cleaned_data.get('stripe_token'):
            self._validate_card(cleaned_data)
        return cleaned_data

    def _validate_card(self, data):
        required_fields = ['card_number', 'card_holder', 'expiry_month', 'expiry_year', 'cvv']
        for field in required_fields:
            if not data.get(field):
                self.add_error(field, f'{field.replace("_", " ").capitalize()} is required')

        card_number = data.get('card_number', '').replace(' ', '')
        if card_number and (not card_number.isdigit() or not (13 <= len(card_number) <= 19)):
            self.add_error('card_number', 'Card number should be 13–19 digits')
        elif card_number and not self._is_valid_luhn(card_number):
            self.add_error('card_number', 'Invalid card number')

        cvv = data.get('cvv', '')
        if cvv and (not cvv.isdigit() or not (3 <= len(cvv) <= 4)):
            self.add_error('cvv', 'CVV must be 3 or 4 digits')

    def _is_valid_luhn(self, card_number):
        digits = [int(d) for d in card_number]
        checksum = sum(digits[-1::-2]) + sum(sum(divmod(d * 2, 10)) for d in digits[-2::-2])
        return checksum % 10 == 0


class BookingForm(StudentDiscountMixin, forms.Form):
    pass  # Логика уже в миксине
