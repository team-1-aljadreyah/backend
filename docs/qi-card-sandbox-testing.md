# Qi Card Sandbox Testing Guide — Test Cards & Scenarios

## 1. Official Sandbox Test Credentials

The Qi Card sandbox environment accepts the following test cards for verifying payment flows:

### Successful Payment Cards
| Card Number | Expiry | CVV | 3DS OTP | Expected Result |
| ----------- | ------ | --- | ------- | --------------- |
| `5213720304238582` | `01/32` | `642` | `123123` | `SUCCESS` (Full approval) |
| `5213720304238590` | `01/32` | `642` | `123123` | `SUCCESS` (Full approval) |

### Error & Edge Case Cards
| Card Number | Expiry | CVV | Behavior / Expected Result |
| ----------- | ------ | --- | -------------------------- |
| `5213720304238608` | `01/32` | `642` | Declines with `FAILED` (Insufficient Funds) |
| `5213720304238616` | `01/32` | `642` | Declines with `AUTHENTICATION_FAILED` (Bad OTP) |
| `5213720304238624` | `01/32` | `642` | Simulates expired card rejection |

---

## 2. End-to-End Testing Scenarios

### Scenario A: Booking and Online Deposit Payment
1. Patient initiates booking via `POST /appointments` with `pay: "deposit"` or `pay: "full"`.
2. Backend generates a `PaymentSession` and calls Qi Card `POST /payment`.
3. Response returns `form_url` redirecting the patient to the sandbox payment page.
4. Complete payment using Card `5213720304238582` and OTP `123123`.
5. Gateway redirects to `finishPaymentUrl` and triggers `POST /payments/qi-webhook`.
6. Backend verifies signature and authoritative status, settles invoice, marks session `success`, clears `pay_by` deadline, and emits `payment.settled` outbox event.

### Scenario B: Failed 3D-Secure Authentication
1. Patient enters Card `5213720304238616` or submits an incorrect OTP.
2. Gateway reports `AUTHENTICATION_FAILED`.
3. Backend marks `payment_sessions.status = "authentication_failed"`.
4. The appointment remains in `booked` status until `pay_by` expiration, allowing the patient to retry payment.

### Scenario C: Cancellation and Automatic Online Refund
1. Patient cancels appointment with a settled online payment via `POST /appointments/{id}/cancel`.
2. Backend identifies settled online transaction in `payments` ledger.
3. Automatically issues `POST /payment/{payment_id}/refund` to the Qi Card gateway.
4. Records corresponding `reversal` entry in `payments` table and logs audit record.

### Scenario D: Administrative Reversal & Partial Refund
1. Staff with `accountant` or `manager` role calls `POST /payments/{id}/reverse` with justification `reason`.
2. Backend invokes `qi_gateway.refund_payment`.
3. Ledger records reversal line and publishes outbox event.
