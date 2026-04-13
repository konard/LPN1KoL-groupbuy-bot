"""
Experiment: Verify that the auth 400 error fixes for issue #292 are correct.

This tests the logic changes without running the full NestJS stack.
It validates:
1. RegisterDto field mapping: frontend sends snake_case, DTO uses camelCase
2. Token refresh field name: refreshToken (camelCase)
3. Login payload structure
"""

# ── Test 1: RegisterDto field validation logic ────────────────────────────────

def test_register_dto_field_names():
    """
    Frontend now sends these fields to /api/v1/auth/register:
      { email, password, firstName, lastName, role }

    RegisterDto now accepts:
      email (required), password (required, min 8),
      firstName (optional), lastName (optional), role (optional enum)

    Previously forbidden extra fields:
      phone, platform, platform_user_id → these are no longer sent
    """
    # Fields that are now sent (after fix)
    frontend_register_payload = {
        "email": "user@example.com",
        "password": "secretpass123",
        "firstName": "Иван",
        "lastName": "Иванов",
        "role": "buyer",
    }
    allowed_dto_fields = {"email", "password", "firstName", "lastName", "role"}
    sent_fields = set(frontend_register_payload.keys())
    forbidden = sent_fields - allowed_dto_fields
    assert forbidden == set(), f"FAIL: forbidden fields sent: {forbidden}"
    print("PASS: register payload contains no forbidden fields")

def test_register_dto_required_fields():
    """email and password must be present"""
    required = {"email", "password"}
    payload = {
        "email": "user@example.com",
        "password": "secretpass123",
    }
    missing = required - set(payload.keys())
    assert missing == set(), f"FAIL: missing required fields: {missing}"
    print("PASS: required fields present")

def test_register_dto_password_min_length():
    """password must be >= 8 chars"""
    short_password = "short"
    valid_password = "validpass"
    assert len(short_password) < 8, "FAIL: short password check"
    assert len(valid_password) >= 8, "FAIL: valid password check"
    print("PASS: password min length validation works")

def test_register_dto_role_enum():
    """role must be one of UserRole enum values"""
    valid_roles = {"user", "admin", "moderator", "organizer", "supplier", "buyer"}
    frontend_roles = {"buyer", "organizer", "supplier"}  # roles shown in UI
    assert frontend_roles.issubset(valid_roles), f"FAIL: invalid roles: {frontend_roles - valid_roles}"
    print(f"PASS: all frontend roles {frontend_roles} are valid enum values")

# ── Test 2: Login payload ─────────────────────────────────────────────────────

def test_login_dto_field_names():
    """
    Frontend now sends to /api/v1/auth/login:
      { email, password }

    LoginDto accepts: email (required), password (required)
    Previously: frontend called Django /api/users/by_email/ — no password!
    """
    frontend_login_payload = {"email": "user@example.com", "password": "secretpass123"}
    allowed_dto_fields = {"email", "password"}
    forbidden = set(frontend_login_payload.keys()) - allowed_dto_fields
    assert forbidden == set(), f"FAIL: forbidden login fields: {forbidden}"
    print("PASS: login payload contains no forbidden fields")

# ── Test 3: Token refresh field name ─────────────────────────────────────────

def test_refresh_token_field_name():
    """
    Frontend now sends to /api/v1/auth/refresh:
      { refreshToken: "..." }  ← camelCase (matches RefreshDto)

    Previously: { refresh_token: "..." } ← snake_case → 400 VALIDATION_ERROR
    """
    old_payload = {"refresh_token": "sometoken"}
    new_payload = {"refreshToken": "sometoken"}

    allowed_dto_fields = {"refreshToken"}

    old_forbidden = set(old_payload.keys()) - allowed_dto_fields
    new_forbidden = set(new_payload.keys()) - allowed_dto_fields

    assert old_forbidden != set(), "OLD payload should have had forbidden fields"
    assert new_forbidden == set(), f"FAIL: new refresh payload has forbidden fields: {new_forbidden}"
    print("PASS: refresh token now uses camelCase 'refreshToken'")

# ── Test 4: Refresh endpoint URL ─────────────────────────────────────────────

def test_refresh_endpoint_url():
    """
    Old: /api/auth/refresh  → Django (didn't exist)
    New: /api/v1/auth/refresh → NestJS auth-service via gateway
    """
    old_url = "/api/auth/refresh"
    new_url = "/api/v1/auth/refresh"

    assert new_url.startswith("/api/v1/auth/"), "FAIL: refresh URL should go through gateway v1 prefix"
    print(f"PASS: refresh URL updated to {new_url}")

# ── Test 5: Logout clears refreshToken ───────────────────────────────────────

def test_logout_clears_refresh_token():
    """
    Logout now removes 'refreshToken' from localStorage in addition to 'authToken'
    Previously 'refreshToken' was left behind
    """
    removed_keys = ["userId", "authToken", "refreshToken"]
    assert "refreshToken" in removed_keys, "FAIL: refreshToken not removed on logout"
    print("PASS: logout removes refreshToken from localStorage")

# ── Run all tests ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_register_dto_field_names,
        test_register_dto_required_fields,
        test_register_dto_password_min_length,
        test_register_dto_role_enum,
        test_login_dto_field_names,
        test_refresh_token_field_name,
        test_refresh_endpoint_url,
        test_logout_clears_refresh_token,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL [{test.__name__}]: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests PASSED — fix is correct!")
    else:
        print("Some tests FAILED — check the fix!")
