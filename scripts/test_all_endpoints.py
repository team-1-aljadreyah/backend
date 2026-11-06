import urllib.request
import urllib.error
import json
import sys

base_url = "https://api.ama8.uk"

roles = [
    ("Reception", "07701234567", "Reception123!"),
    ("Doctor", "07702345678", "Doctor123!"),
    ("Pharmacy", "07703456789", "Pharmacy123!"),
    ("Laboratory", "07704567890", "Lab123!"),
    ("Accountant", "07705678901", "Accountant123!"),
    ("Manager", "07706789012", "Manager123!"),
    ("Patient", "07707890123", "Patient123!"),
]

def make_request(path, token=None, method="GET", data=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            res_body = res.read().decode("utf-8")
            try:
                parsed = json.loads(res_body)
            except Exception:
                parsed = res_body
            return res.status, parsed
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return e.code, parsed
    except Exception as e:
        return 0, str(e)

print("1. Authenticating all roles...")
tokens = {}
for role, phone, pw in roles:
    st, resp = make_request("/auth/login", method="POST", data={"phone": phone, "password": pw})
    if st == 200 and resp.get("success"):
        tokens[role] = resp["data"]["access_token"]
        print(f"  [OK] {role} ({phone})")
    else:
        print(f"  [FAIL] {role}: {st} -> {resp}")

tests = [
    # Public endpoints
    ("Public", None, "GET", "/health"),
    ("Public", None, "GET", "/public/doctors"),
    ("Public", None, "GET", "/public/queue-screen"),
    
    # Manager endpoints
    ("Manager", "Manager", "GET", "/manager/overview"),
    ("Manager", "Manager", "GET", "/manager/analytics?days=7"),
    ("Manager", "Manager", "GET", "/users"),
    ("Manager", "Manager", "GET", "/audit?limit=10&offset=0"),
    ("Manager", "Manager", "GET", "/settings"),
    ("Manager", "Manager", "GET", "/reports/daily"),
    ("Manager", "Manager", "GET", "/reports/doctors"),
    ("Manager", "Manager", "GET", "/welfare?status=pending"),
    
    # Reception endpoints
    ("Reception", "Reception", "GET", "/appointments/today"),
    ("Reception", "Reception", "GET", "/patients?limit=10&offset=0"),
    ("Reception", "Reception", "GET", "/cash/current"),
    ("Reception", "Reception", "GET", "/cash/closings"),
    ("Reception", "Reception", "GET", "/welfare"),
    
    # Doctor endpoints
    ("Doctor", "Doctor", "GET", "/appointments/today"),
    ("Doctor", "Doctor", "GET", "/patients?limit=5&offset=0"),
    
    # Pharmacy endpoints
    ("Pharmacy", "Pharmacy", "GET", "/prescriptions"),
    ("Pharmacy", "Pharmacy", "GET", "/pharmacy/stock"),
    ("Pharmacy", "Pharmacy", "GET", "/pharmacy/catalog"),
    ("Pharmacy", "Pharmacy", "GET", "/pharmacy/sales"),
    ("Pharmacy", "Pharmacy", "GET", "/pharmacy/stock/log"),
    
    # Lab endpoints
    ("Laboratory", "Laboratory", "GET", "/lab/orders"),
    
    # Accountant endpoints
    ("Accountant", "Accountant", "GET", "/ledger?limit=10&offset=0"),
    ("Accountant", "Accountant", "GET", "/expenses"),
    ("Accountant", "Accountant", "GET", "/cash/closings"),
    
    # Patient endpoints
    ("Patient", "Patient", "GET", "/me/appointments"),
    ("Patient", "Patient", "GET", "/me/family"),
    ("Patient", "Patient", "GET", "/me/payments?limit=10&offset=0"),
    ("Patient", "Patient", "GET", "/me/welfare"),
    ("Patient", "Patient", "GET", "/me/notifications"),
]

print("\n2. Testing all core endpoints...")
failed = 0
for group, role_key, method, path in tests:
    token = tokens.get(role_key) if role_key else None
    st, resp = make_request(path, token=token, method=method)
    if st == 200:
        # Check if success field is True when dict
        ok = resp.get("success", True) if isinstance(resp, dict) else True
        if ok:
            print(f"  [OK 200] {group:10} {method:4} {path}")
        else:
            print(f"  [WARN 200 but success=False] {group:10} {method:4} {path} -> {resp}")
            failed += 1
    else:
        print(f"  [FAIL {st}] {group:10} {method:4} {path} -> {resp}")
        failed += 1

print(f"\nCompleted {len(tests)} endpoint tests. Failures: {failed}")
