"""
Эксперимент: проверка исправлений для задачи #202.

Корень проблемы #202:
  PR #201 исправлял `gateway/main.py`, но docker-compose.yml собирает gateway
  из `./services/gateway`, поэтому исправления не попадали в реально
  используемый образ. После `docker compose up --build -d` все 3 проблемы
  из задачи #200 оставались:
    1. /api/v1/auth/register и /api/v1/auth/login возвращали 401
    2. Маршруты микросервисов отсутствовали в Swagger UI
    3. Описания в Swagger были на английском

Исправление:
  Применить тот же набор изменений к services/gateway/main.py — именно этот
  файл копируется в образ Dockerfile-ом и используется в docker-compose.yml.

Эта проверка загружает services/gateway/main.py через TestClient FastAPI
и убеждается, что:
  * /api/v1/auth/login и /api/v1/auth/register НЕ возвращают 401 без токена
    (вместо этого корректно проксируют в auth-service, которого нет
    в тестовом окружении → 502, что подтверждает прохождение auth-проверки).
  * /api/v1/auth/me БЕЗ токена возвращает 401 (корректное поведение).
  * OpenAPI-схема содержит все ожидаемые эндпоинты микросервисов.
  * Описание API на русском языке.
"""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_PATH = ROOT / "services" / "gateway" / "main.py"


def _load_gateway_module():
    spec = importlib.util.spec_from_file_location("gateway_main", str(GATEWAY_PATH))
    module = importlib.util.module_from_spec(spec)
    sys.modules["gateway_main"] = module
    spec.loader.exec_module(module)
    return module


def test_swagger_has_microservice_endpoints():
    gw = _load_gateway_module()
    schema = gw.app.openapi()
    paths = schema.get("paths", {})

    expected = [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/purchases",
        "/api/v1/payments/wallets/me",
        "/api/v1/chat/rooms",
        "/api/v1/reputation/reviews",
        "/api/v1/search/search",
        "/api/v1/analytics/stats/summary",
    ]
    missing = [p for p in expected if p not in paths]
    assert not missing, f"Отсутствуют пути в Swagger: {missing}"
    print(f"PASS: Swagger содержит {len(expected)} ожидаемых эндпоинтов микросервисов")


def test_swagger_description_is_russian():
    gw = _load_gateway_module()
    schema = gw.app.openapi()
    info = schema.get("info", {})
    description = info.get("description", "")
    # Кириллические символы должны присутствовать в описании
    has_cyrillic = any("Ѐ" <= ch <= "ӿ" for ch in description)
    assert has_cyrillic, f"Описание API не на русском: {description!r}"
    print(f"PASS: описание API содержит кириллицу: {description[:60]}...")


def test_auth_login_does_not_return_401_without_token():
    """
    Главная проверка #200/#202:
    /api/v1/auth/login должен быть публичным — без токена не должно быть 401.
    Без живого auth-service запрос вернёт 502 (Upstream недоступен), но это
    подтверждает: gateway пропустил его дальше, не отбросил по auth.
    """
    from fastapi.testclient import TestClient

    # Принудительно отключаем Redis в lifespan, задав битый URL
    os.environ["REDIS_URL"] = "redis://localhost:1/0"
    # Указываем недоступный auth-service, чтобы запрос вернул 502, а не уходил наружу
    os.environ["AUTH_SERVICE_URL"] = "http://auth-service-not-running.invalid:4001"

    gw = _load_gateway_module()
    with TestClient(gw.app) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "secret"},
        )
        assert resp.status_code != 401, (
            f"FAIL: /api/v1/auth/login без токена возвращает 401: {resp.text}"
        )
        # 502 означает: auth-проверка пройдена, но upstream недоступен — норма для теста.
        assert resp.status_code in (502, 503), (
            f"Ожидался 502 (upstream недоступен), получен {resp.status_code}: {resp.text}"
        )
        print(f"PASS: /api/v1/auth/login без токена -> {resp.status_code} (не 401)")

        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "secret"},
        )
        assert resp.status_code != 401, (
            f"FAIL: /api/v1/auth/register без токена возвращает 401: {resp.text}"
        )
        print(f"PASS: /api/v1/auth/register без токена -> {resp.status_code} (не 401)")


def test_auth_me_requires_token():
    """/api/v1/auth/me должен возвращать 401 без токена."""
    from fastapi.testclient import TestClient

    os.environ["REDIS_URL"] = "redis://localhost:1/0"
    os.environ["AUTH_SERVICE_URL"] = "http://auth-service-not-running.invalid:4001"

    gw = _load_gateway_module()
    with TestClient(gw.app) as client:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401, (
            f"FAIL: /api/v1/auth/me без токена должен возвращать 401, получен {resp.status_code}"
        )
        print("PASS: /api/v1/auth/me без токена -> 401 (требует аутентификации)")


def test_health_endpoint():
    """/health должен возвращать 200 без аутентификации."""
    from fastapi.testclient import TestClient

    os.environ["REDIS_URL"] = "redis://localhost:1/0"
    gw = _load_gateway_module()
    with TestClient(gw.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200, f"FAIL: /health -> {resp.status_code}"
        body = resp.json()
        assert body.get("status") == "ok"
        print("PASS: /health -> 200")


if __name__ == "__main__":
    tests = [
        test_swagger_has_microservice_endpoints,
        test_swagger_description_is_russian,
        test_health_endpoint,
        test_auth_me_requires_token,
        test_auth_login_does_not_return_401_without_token,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL [{t.__name__}]: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR [{t.__name__}]: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Результат: {passed} прошло, {failed} не прошло")
    if failed == 0:
        print("Все тесты ПРОШЛИ — исправление #202 корректно!")
    else:
        print("Некоторые тесты НЕ ПРОШЛИ — проверьте исправление!")
        sys.exit(1)
