import os
import requests

# Test API URL
CASHFREE_BASE_URL = "https://sandbox.cashfree.com/pg/orders"

# YAHAN APNI KEYS DAALNA:
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")

def create_cashfree_order(order_id: str, amount: float, customer_id: str, customer_phone: str, customer_email: str):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-version": "2023-08-01",
        "x-client-id": CLIENT_ID,
        "x-client-secret": CLIENT_SECRET
    }
    
    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "customer_phone": customer_phone
        },
        "order_meta": {
            "return_url": f"http://localhost:3000/dashboard?order_id={order_id}"
        }
    }
    
    response = requests.post(CASHFREE_BASE_URL, json=payload, headers=headers)
    return response.json()