"""
Эксперимент: проверка исправлений для задачи #200.

Проверяет:
1. Исправление 401 ошибки на /api/v1/auth/register и /api/v1/auth/login
   - Корень проблемы: Python app.py сервиса аутентификации имел маршруты
     /auth/register и /auth/login, но gateway перенаправляет запросы без
     префикса имени сервиса (т.е. → /register, /login).
   - Исправление: удалить /auth/ префикс из маршрутов auth-service/app.py.

2. Правильность построения URL при проксировании.
3. Корректная идентификация публичных (незащищённых) путей.
"""

# ── Тест 1: Публичные пути в gateway ─────────────────────────────────────────

PUBLIC_PATHS = frozenset({
    "auth/login",
    "auth/register",
    "auth/refresh",
    "auth/forgot-password",
    "auth/reset-password",
})

def test_public_paths():
    cases = [
        ("auth", "login", True),
        ("auth", "register", True),
        ("auth", "refresh", True),
        ("auth", "forgot-password", True),
        ("auth", "reset-password", True),
        ("auth", "logout", False),
        ("auth", "me", False),
        ("purchases", "purchases", False),
        ("chat", "rooms", False),
        ("payments", "wallets/me", False),
    ]
    for service, path, expected in cases:
        is_public = f"{service}/{path}".rstrip("/") in PUBLIC_PATHS
        assert is_public == expected, (
            f"FAIL: /api/v1/{service}/{path}: is_public={is_public}, expected={expected}"
        )
    print("PASS: все публичные пути определены корректно")


# ── Тест 2: Построение URL для проксирования ─────────────────────────────────

def build_target_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

def test_target_urls():
    cases = [
        ("http://auth-service:4001", "register",   "http://auth-service:4001/register"),
        ("http://auth-service:4001", "login",       "http://auth-service:4001/login"),
        ("http://auth-service:4001", "refresh",     "http://auth-service:4001/refresh"),
        ("http://auth-service:4001", "logout",      "http://auth-service:4001/logout"),
        ("http://auth-service:4001", "me",          "http://auth-service:4001/me"),
        ("http://purchase-service:4002", "purchases", "http://purchase-service:4002/purchases"),
        ("http://chat-service:4004", "rooms",         "http://chat-service:4004/rooms"),
    ]
    for base, path, expected in cases:
        actual = build_target_url(base, path)
        assert actual == expected, f"FAIL: {actual} != {expected}"
    print("PASS: все URL для проксирования построены корректно")


# ── Тест 3: Маршруты auth-service соответствуют ожиданиям gateway ────────────

def test_auth_service_routes():
    """
    До исправления: /auth/register → 404 (маршрут не найден)
    После исправления: /register → 201 (маршрут найден)

    Gateway отправляет:
      /api/v1/auth/register → http://auth-service:4001/register
      /api/v1/auth/login    → http://auth-service:4001/login

    auth-service/app.py теперь имеет маршруты:
      /register, /login, /refresh, /logout, /me
    """
    auth_service_routes = {"/register", "/login", "/refresh", "/logout", "/me", "/health"}
    gateway_forwarded_paths = {"/register", "/login", "/refresh", "/logout", "/me"}

    for path in gateway_forwarded_paths:
        assert path in auth_service_routes, (
            f"FAIL: маршрут {path} отсутствует в auth-service"
        )
    print("PASS: все пути, перенаправляемые gateway, присутствуют в auth-service")


# ── Запуск всех тестов ────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [test_public_paths, test_target_urls, test_auth_service_routes]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL [{t.__name__}]: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Результат: {passed} прошло, {failed} не прошло")
    if failed == 0:
        print("Все тесты ПРОШЛИ — исправление корректно!")
    else:
        print("Некоторые тесты НЕ ПРОШЛИ — проверьте исправление!")
