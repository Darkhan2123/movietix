from decimal import Decimal
from django.conf import settings
import stripe
import logging
import re
import os

logger = logging.getLogger(__name__)

# Use Stripe test key from settings with a fallback
stripe_api_key = settings.STRIPE_SECRET_KEY

# If no key is set in settings, use a test key
if not stripe_api_key:
    # Test key for development purposes only
    stripe_api_key = 'sk_test_51OXRaZC7mCB2KYLpnZHO0XUwlwgpk5FkxAD5SpOH2AJGbW8GlNjm3TL4YJzUVvA6HEG2WXPARnUcZAh3Ot9qAcaZ00AoO8PwOR'
    logger.warning("Using fallback test Stripe API key. This should not be used in production.")

# Set the API key for the stripe module
stripe.api_key = stripe_api_key

# Log key (partially masked) for debugging
logger.info(f"Stripe API key configured: {stripe_api_key[:4]}...{stripe_api_key[-4:]}")

class PaymentService:
    @staticmethod
    def create_payment_intent(booking):
        """Create a payment intent for the booking with idempotency key"""
        try:
            # Validate booking
            if not booking or not booking.id:
                logger.error("Invalid booking object provided to create_payment_intent")
                raise PaymentError("Invalid booking information")

            # Validate booking status
            if booking.status != 'pending':
                logger.error(f"Cannot create payment for booking {booking.id} with status {booking.status}")
                raise PaymentError(f"Cannot process payment for booking with status: {booking.status}")

            # Convert total price to cents for Stripe
            try:
                amount = int(booking.total_price * 100)
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting booking amount: {e}")
                raise PaymentError("Invalid booking amount format")

            # Ensure we have a valid amount
            if amount <= 0:
                logger.error(f"Invalid booking amount: {amount} cents")
                raise PaymentError("Invalid booking amount")

            # Prepare metadata with safe values
            metadata = {
                'booking_id': str(booking.id),
                'user_id': str(booking.user.id),
                'showtime_id': str(booking.showtime.id),
                'created_at': booking.booking_time.isoformat() if booking.booking_time else '',
                'seats': ','.join(booking.seats.split(',')[:5]) + ('...' if len(booking.seats.split(',')) > 5 else '')
            }

            # Truncate movie title if needed (Stripe metadata values have a limit)
            movie_title = booking.showtime.movie.title
            if movie_title:
                if len(movie_title) > 40:  # Stripe has limits on metadata value size
                    metadata['movie'] = movie_title[:37] + '...'
                else:
                    metadata['movie'] = movie_title

            # Create idempotency key based on booking ID to prevent duplicate charges
            idempotency_key = f"booking_{booking.id}_{int(booking.total_price * 100)}"

            # Create the payment intent with Stripe using idempotency key
            max_retries = 3
            retry_count = 0
            last_error = None

            while retry_count < max_retries:
                try:
                    intent = stripe.PaymentIntent.create(
                        amount=amount,
                        currency='usd',
                        metadata=metadata,
                        # Add statement descriptor for better user experience
                        statement_descriptor_suffix='MovieTix',
                        # Add idempotency key to prevent duplicate charges
                        idempotency_key=idempotency_key
                    )

                    logger.info(f"Created payment intent {intent.id} for booking {booking.id}")
                    return {
                        'client_secret': intent.client_secret,
                        'payment_id': intent.id
                    }
                except (stripe.error.APIConnectionError, stripe.error.ServiceUnavailableError) as e:
                    # These are retryable errors
                    retry_count += 1
                    last_error = e
                    logger.warning(f"Retryable error creating payment intent (attempt {retry_count}/{max_retries}): {str(e)}")
                    import time
                    time.sleep(1)  # Wait before retrying
                except stripe.error.StripeError as e:
                    # Other Stripe errors are not retried
                    logger.error(f"Stripe error creating payment intent: {str(e)}")
                    raise PaymentError(str(e))

            # If we get here, we've exhausted our retries
            logger.error(f"Failed to create payment intent after {max_retries} retries: {str(last_error)}")
            raise PaymentError(f"Payment service temporarily unavailable. Please try again later.")

        except stripe.error.StripeError as e:
            # Log the error and raise it for the view to handle
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise PaymentError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error in create_payment_intent: {str(e)}")
            raise PaymentError("An unexpected error occurred during payment processing")

    @staticmethod
    def confirm_payment(payment_id, booking=None):
        """Confirm that a payment was successful and verify amount if booking provided"""
        try:
            # Validate payment_id format
            if not payment_id:
                logger.error("No payment ID provided")
                raise PaymentError("No payment ID provided")

            # Basic validation of payment_id format (Stripe payment IDs start with 'pi_')
            if not isinstance(payment_id, str) or not re.match(r'^pi_[a-zA-Z0-9]+$', payment_id):
                logger.error(f"Invalid payment ID format: {payment_id}")
                raise PaymentError("Invalid payment ID format")

            # Retrieve the payment intent from Stripe
            payment_intent = stripe.PaymentIntent.retrieve(payment_id)

            # Log payment status
            logger.info(f"Payment {payment_id} status: {payment_intent.status}")

            # Check for successful payment
            is_successful = payment_intent.status == 'succeeded'
            if not is_successful:
                logger.warning(f"Payment {payment_id} not successful. Status: {payment_intent.status}")
                return False

            # Verify payment amount if booking is provided
            if booking and is_successful:
                expected_amount = int(booking.total_price * 100)
                actual_amount = payment_intent.amount

                if expected_amount != actual_amount:
                    logger.error(f"Payment amount mismatch: expected {expected_amount} cents, got {actual_amount} cents")
                    raise PaymentError(f"Payment amount mismatch: expected ${booking.total_price}, got ${actual_amount/100}")

            return is_successful

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            raise PaymentError(str(e))
        except Exception as e:
            logger.error(f"Unexpected error in confirm_payment: {str(e)}")
            raise PaymentError("An unexpected error occurred during payment confirmation")

    @staticmethod
    def get_payment_status(payment_id):
        """Get detailed status of a payment"""
        try:
            if not payment_id:
                return {'status': 'unknown', 'message': 'No payment ID provided'}

            payment_intent = stripe.PaymentIntent.retrieve(payment_id)
            return {
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,  # Convert from cents to dollars
                'currency': payment_intent.currency,
                'created': payment_intent.created,
                'metadata': payment_intent.metadata
            }
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            return {'status': 'error', 'message': str(e)}

class PaymentError(Exception):
    """Custom exception for payment-related errors"""
    pass


