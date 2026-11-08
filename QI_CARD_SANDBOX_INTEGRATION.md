# Official Qi Card Payment Gateway — Sandbox Integration Guide

## 1. Gateway Overview

The Al-Jadreyah Clinic backend integrates with the **Official Qi Card Payment Gateway Sandbox** (International Smart Card — ISC Iraq) to support secure 3D-Secure card payments.

### Sandbox Environment Details
- **Base URL:** `https://uat-sandbox-3ds-api.qi.iq/api/v1`
- **Merchant Username:** `paymentgatewaytest`
- **Merchant Password:** `WHaNFE5C3qlChqNbAzH4`
- **Terminal ID:** `237984`
- **Currency:** `IQD` (Iraqi Dinar)
- **Locale:** `ar_IQ`

---

## 2. Authentication & Headers

Every request sent to the Qi Card API must include HTTP Basic Authentication and the assigned terminal ID header:

```http
Authorization: Basic cGF5bWVudGdhdGV3YXl0ZXN0OldIYU5GRTVDM3FsQ2hRTmJBelg0
X-Terminal-Id: 237984
Content-Type: application/json
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Al-Rahma-Clinic/1.0
```

---

## 3. Supported API Endpoints

### 3.1 Initiate Payment (`POST /payment`)
Creates a hosted payment session and returns a checkout redirect URL (`formUrl`).

**Request Payload:**
```json
{
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 25000.0,
  "currency": "IQD",
  "locale": "ar_IQ",
  "finishPaymentUrl": "https://alrahma.ama8.uk/account/payment?payment=550e8400...",
  "notificationUrl": "https://api.ama8.uk/payments/qi-webhook",
  "appChannel": false
}
```

**Response Payload:**
```json
{
  "paymentId": "240321123456",
  "formUrl": "https://uat-sandbox-3ds-api.qi.iq/payment-page?id=240321123456"
}
```

### 3.2 Query Payment Status (`GET /payment/{payment_id}/status`)
Queries the authoritative status of a transaction on the gateway.

**Response Status Values:**
- `SUCCESS`: Payment successfully authorized and captured.
- `FAILED`: Card declined or invalid parameters.
- `AUTHENTICATION_FAILED`: 3DS OTP verification failed.
- `CANCELLED`: Payment cancelled by user or merchant.

### 3.3 Refund Transaction (`POST /payment/{payment_id}/refund`)
Initiates a full or partial refund for a processed payment.

**Request Payload:**
```json
{
  "requestId": "refund-req-001",
  "amount": 25000.0,
  "message": "Appointment cancelled by patient"
}
```

### 3.4 Cancel Pending Payment (`POST /payment/{payment_id}/cancel`)
Cancels an uncompleted payment transaction on the gateway.

---

## 4. Webhook Handling & Signature Verification

Upon transaction completion, Qi Card issues an HTTP POST to `POST /payments/qi-webhook` with an `X-Signature` header.

### Canonical Signature String
The signature is verified using RSA-SHA256 against the canonical string format:
```
paymentId|amount.000|currency|creationDate|status
```
Example: `240321123456|25000.000|IQD|2026-11-08T15:30:00Z|SUCCESS`

### Authoritative Server-to-Server Fallback
If the webhook public key (`QI_WEBHOOK_PUBLIC_KEY_PEM`) is not yet provisioned by Qi Card merchant support, the backend authoritatively queries `GET /payment/{id}/status` server-to-server before settling the invoice, preventing unverified client updates.

---

## 5. Strict Decimal Financial Handling

1. All monetary values are processed using Python's `decimal.Decimal` to prevent binary floating-point rounding errors.
2. Invoices reject zero or negative payment amounts (`zero_balance`).
3. Overpayments beyond outstanding appointment balance are strictly refused.
