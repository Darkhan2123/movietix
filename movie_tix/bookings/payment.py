from decimal import Decimal
from django.conf import settings
import logging
import requests

logger = logging.getLogger(__name__)

class PaymentError(Exception):
    pass

class PaymentService:
    BASE_URL = "http://localhost:8001"

    def confirm_payment(self, payment_id):
        """
        Проверяет статус платежа по task_id (payment_id).
        Возвращает True, если статус 'confirmed' или 'succeeded'.
        """
        try:
            resp = requests.get(f"{self.BASE_URL}/{payment_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            return status in ("confirmed", "succeeded")
        except Exception as e:
            raise PaymentError(f"Ошибка при проверке платежа: {e}")

    def get_payment_status(self, payment_id):
        """
        Получить подробный статус платежа.
        """
        try:
            resp = requests.get(f"{self.BASE_URL}/{payment_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise PaymentError(f"Ошибка при получении статуса платежа: {e}")

    def create_payment_session(self, payload):
        """
        Создать сессию оплаты (POST /).
        """
        try:
            resp = requests.post(f"{self.BASE_URL}/", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise PaymentError(f"Ошибка при создании сессии оплаты: {e}")