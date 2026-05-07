"""FastAPI API gateway для стека микросервисов GroupBuy.

Реализует контракт, описанный в задаче #178:

* Слушает порт `${PORT}` (по умолчанию 3000).
* Маршрутизирует `/api/v1/{service}/{path:path}` к соответствующему
  upstream URL, определяемому из переменных окружения `${SERVICE}_SERVICE_URL`.
* Проверяет JWT в заголовке `Authorization: Bearer <token>` с использованием
  `JWT_SECRET`. Белый список публичных путей (например, `/api/v1/auth/login`)
  освобождён от проверки.
* Ограничение запросов по IP (или по user_id при аутентификации) через Redis
  с фиксированным окном `${RATE_LIMIT_RPM}` rpm.
* CORS middleware конфигурируется через `CORS_ORIGINS` (через запятую).
* `GET /health` возвращает 200 для docker healthcheck.

Примечание для фронтенда (задача #178, раздел 3): React-контейнер
должен обращаться к gateway, например `API_BASE_URL=http://gateway:3000`,
а не напрямую к `core:8000`.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Iterable

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt

# ─── Конфигурация ─────────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "3000"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

REDIS_ADDR = os.getenv("REDIS_ADDR", "redis:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_URL = os.getenv(
    "REDIS_URL",
    f"redis://{':' + REDIS_PASSWORD + '@' if REDIS_PASSWORD else ''}{REDIS_ADDR}/0",
)

SERVICE_URLS: dict[str, str] = {
    "auth":          os.getenv("AUTH_SERVICE_URL",          "http://auth-service:4001"),
    "purchases":     os.getenv("PURCHASE_SERVICE_URL",      "http://purchase-service:4002"),
    "payments":      os.getenv("PAYMENT_SERVICE_URL",       "http://payment-service:4003"),
    "chat":          os.getenv("CHAT_SERVICE_URL",          "http://chat-service:4004"),
    "notifications": os.getenv("NOTIFICATION_SERVICE_URL",  "http://notification-service:4005"),
    "analytics":     os.getenv("ANALYTICS_SERVICE_URL",     "http://analytics-service:4006"),
    "search":        os.getenv("SEARCH_SERVICE_URL",        "http://search-service:4007"),
    "reputation":    os.getenv("REPUTATION_SERVICE_URL",    "http://reputation-service:4008"),
}

# Пути под /api/v1, не требующие JWT.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "auth/login",
        "auth/login/confirm",
        "auth/register",
        "auth/register/confirm",
        "auth/refresh",
        "auth/resend-code",
        "auth/forgot-password",
        "auth/reset-password",
    }
)

# Заголовки, которые не должны пересылаться в upstream сервисы или обратно клиенту.
HOP_BY_HOP_HEADERS: frozenset[str] = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("gateway")


# ─── Lifespan: общий httpx клиент + Redis клиент ─────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
    try:
        app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await app.state.redis.ping()
        logger.info("Redis готов по адресу %s", REDIS_ADDR)
    except Exception as exc:  # pragma: no cover - logged and degrades gracefully
        logger.warning("Redis недоступен (%s); ограничение запросов отключено", exc)
        app.state.redis = None

    logger.info("Gateway слушает порт :%d", PORT)
    try:
        yield
    finally:
        await app.state.http.aclose()
        if app.state.redis is not None:
            await app.state.redis.aclose()


app = FastAPI(
    title="GroupBuy API Gateway",
    version="1.0.0",
    description=(
        "API Gateway для платформы групповых закупок GroupBuy. "
        "Маршрутизирует запросы к микросервисам: аутентификация, закупки, платежи, "
        "чат, уведомления, аналитика, поиск, репутация."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Вспомогательные функции ──────────────────────────────────────────────────


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def _filter_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {k: v for k, v in headers if k.lower() not in HOP_BY_HOP_HEADERS}


async def _enforce_rate_limit(redis: aioredis.Redis | None, identity: str) -> None:
    """Счётчик с фиксированным окном в минуту. Отключается если Redis недоступен."""
    if redis is None:
        return
    key = f"ratelimit:{identity}"
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Redis INCR failed (%s); пропуск ограничения для %s", exc, identity)
        return
    if current > RATE_LIMIT_RPM:
        raise HTTPException(status_code=429, detail="Превышен лимит запросов")


async def _proxy_request(
    request: Request,
    service_name: str,
    path: str,
) -> Response:
    """Основная логика проксирования запроса к upstream сервису."""
    base_url = SERVICE_URLS.get(service_name)
    if base_url is None:
        raise HTTPException(status_code=404, detail=f"Неизвестный сервис '{service_name}'")

    # Аутентификация: требуется, если путь не в PUBLIC_PATHS.
    is_public = f"{service_name}/{path}".rstrip("/") in PUBLIC_PATHS
    claims: dict | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        claims = _decode_jwt(auth_header.split(" ", 1)[1].strip())

    if not is_public and claims is None:
        raise HTTPException(status_code=401, detail="Требуется аутентификация")

    # Ограничение запросов: по userId из токена, иначе по IP.
    identity = (
        f"user:{claims.get('sub')}"
        if claims and claims.get("sub")
        else f"ip:{request.client.host if request.client else 'unknown'}"
    )
    await _enforce_rate_limit(request.app.state.redis, identity)

    # Формирование запроса к upstream.
    target_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    forwarded = _filter_headers(request.headers.items())
    if claims:
        forwarded["x-user-id"] = str(claims.get("sub", ""))
        forwarded["x-user-role"] = str(claims.get("role", "user"))

    body = await request.body()

    try:
        upstream = await request.app.state.http.request(
            method=request.method,
            url=target_url,
            headers=forwarded,
            content=body,
        )
    except httpx.RequestError as exc:
        logger.error("Upstream %s недоступен: %s", target_url, exc)
        raise HTTPException(status_code=502, detail="Upstream сервис недоступен") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_filter_headers(upstream.headers.items()),
        media_type=upstream.headers.get("content-type"),
    )


# ─── Маршруты: служебные ──────────────────────────────────────────────────────


@app.get("/health", tags=["Служебные"], summary="Проверка состояния gateway")
async def health() -> dict[str, str]:
    """Возвращает статус работы gateway. Используется для docker healthcheck."""
    return {"status": "ok", "service": "gateway"}


# ─── Маршруты: Аутентификация ─────────────────────────────────────────────────


@app.post(
    "/api/v1/auth/register",
    tags=["Аутентификация"],
    summary="Регистрация нового пользователя",
    description="Создаёт учётную запись пользователя по email и паролю. Отправляет письмо для подтверждения email.",
)
async def auth_register(request: Request) -> Response:
    return await _proxy_request(request, "auth", "register")


@app.post(
    "/api/v1/auth/login",
    tags=["Аутентификация"],
    summary="Вход в систему — шаг 1",
    description="Принимает номер телефона и отправляет OTP-код на зарегистрированный email пользователя.",
)
async def auth_login(request: Request) -> Response:
    return await _proxy_request(request, "auth", "login")


@app.post(
    "/api/v1/auth/login/confirm",
    tags=["Аутентификация"],
    summary="Вход в систему — шаг 2",
    description="Принимает номер телефона и OTP-код. Возвращает access_token и refresh_token.",
)
async def auth_login_confirm(request: Request) -> Response:
    return await _proxy_request(request, "auth", "login/confirm")


@app.post(
    "/api/v1/auth/register/confirm",
    tags=["Аутентификация"],
    summary="Регистрация — шаг 2",
    description="Принимает номер телефона и OTP-код. Создаёт учётную запись и возвращает токены.",
)
async def auth_register_confirm(request: Request) -> Response:
    return await _proxy_request(request, "auth", "register/confirm")


@app.post(
    "/api/v1/auth/resend-code",
    tags=["Аутентификация"],
    summary="Повторная отправка OTP-кода",
    description="Повторно отправляет OTP-код для текущей сессии входа или регистрации (не чаще одного раза в 30 секунд).",
)
async def auth_resend_code(request: Request) -> Response:
    return await _proxy_request(request, "auth", "resend-code")


@app.post(
    "/api/v1/auth/refresh",
    tags=["Аутентификация"],
    summary="Обновление токена доступа",
    description="Обменивает действующий refresh_token на новую пару access_token / refresh_token.",
)
async def auth_refresh(request: Request) -> Response:
    return await _proxy_request(request, "auth", "refresh")


@app.post(
    "/api/v1/auth/logout",
    tags=["Аутентификация"],
    summary="Выход из системы",
    description="Инвалидирует refresh_token текущего пользователя. Требует действующий Bearer токен.",
)
async def auth_logout(request: Request) -> Response:
    return await _proxy_request(request, "auth", "logout")


@app.get(
    "/api/v1/auth/me",
    tags=["Аутентификация"],
    summary="Информация о текущем пользователе",
    description="Возвращает профиль аутентифицированного пользователя: id, email, телефон, статус верификации.",
)
async def auth_me(request: Request) -> Response:
    return await _proxy_request(request, "auth", "me")


# ─── Маршруты: Закупки ────────────────────────────────────────────────────────


@app.post(
    "/api/v1/purchases",
    tags=["Закупки"],
    summary="Создать закупку",
    description="Создаёт новую групповую закупку. Требует аутентификации.",
    status_code=201,
)
async def purchases_create(request: Request) -> Response:
    return await _proxy_request(request, "purchases", "purchases")


@app.get(
    "/api/v1/purchases",
    tags=["Закупки"],
    summary="Список закупок",
    description="Возвращает список всех доступных групповых закупок.",
)
async def purchases_list(request: Request) -> Response:
    return await _proxy_request(request, "purchases", "purchases")


@app.get(
    "/api/v1/purchases/{purchase_id}",
    tags=["Закупки"],
    summary="Получить закупку по ID",
    description="Возвращает детальную информацию о конкретной закупке.",
)
async def purchases_get(purchase_id: str, request: Request) -> Response:
    return await _proxy_request(request, "purchases", f"purchases/{purchase_id}")


@app.post(
    "/api/v1/purchases/{purchase_id}/voting-sessions",
    tags=["Закупки"],
    summary="Создать сессию голосования",
    description="Создаёт новую сессию голосования для выбора поставщика в закупке.",
    status_code=201,
)
async def purchases_voting_create(purchase_id: str, request: Request) -> Response:
    return await _proxy_request(request, "purchases", f"purchases/{purchase_id}/voting-sessions")


@app.post(
    "/api/v1/purchases/{purchase_id}/voting-sessions/{session_id}/candidates",
    tags=["Закупки"],
    summary="Добавить кандидата в голосование",
    description="Добавляет поставщика-кандидата в активную сессию голосования.",
    status_code=201,
)
async def purchases_voting_candidate(purchase_id: str, session_id: str, request: Request) -> Response:
    return await _proxy_request(
        request, "purchases",
        f"purchases/{purchase_id}/voting-sessions/{session_id}/candidates",
    )


@app.post(
    "/api/v1/purchases/{purchase_id}/voting-sessions/{session_id}/vote",
    tags=["Закупки"],
    summary="Проголосовать за кандидата",
    description="Регистрирует голос пользователя за кандидата в сессии голосования.",
)
async def purchases_voting_vote(purchase_id: str, session_id: str, request: Request) -> Response:
    return await _proxy_request(
        request, "purchases",
        f"purchases/{purchase_id}/voting-sessions/{session_id}/vote",
    )


@app.post(
    "/api/v1/purchases/{purchase_id}/voting-sessions/{session_id}/close",
    tags=["Закупки"],
    summary="Закрыть сессию голосования",
    description="Завершает голосование и фиксирует победившего кандидата.",
)
async def purchases_voting_close(purchase_id: str, session_id: str, request: Request) -> Response:
    return await _proxy_request(
        request, "purchases",
        f"purchases/{purchase_id}/voting-sessions/{session_id}/close",
    )


@app.post(
    "/api/v1/purchases/{purchase_id}/cancel",
    tags=["Закупки"],
    summary="Отменить закупку",
    description="Отменяет групповую закупку и инициирует возврат средств участникам.",
)
async def purchases_cancel(purchase_id: str, request: Request) -> Response:
    return await _proxy_request(request, "purchases", f"purchases/{purchase_id}/cancel")


# ─── Маршруты: Платежи ────────────────────────────────────────────────────────


@app.get(
    "/api/v1/payments/wallets/me",
    tags=["Платежи"],
    summary="Баланс кошелька",
    description="Возвращает баланс кошелька аутентифицированного пользователя.",
)
async def payments_wallet_me(request: Request) -> Response:
    return await _proxy_request(request, "payments", "wallets/me")


@app.post(
    "/api/v1/payments/wallets/topup",
    tags=["Платежи"],
    summary="Пополнить кошелёк",
    description="Инициирует пополнение кошелька пользователя через платёжный шлюз.",
)
async def payments_wallet_topup(request: Request) -> Response:
    return await _proxy_request(request, "payments", "wallets/topup")


@app.post(
    "/api/v1/payments/wallets/hold",
    tags=["Платежи"],
    summary="Заморозить средства",
    description="Замораживает указанную сумму на кошельке для участия в закупке.",
)
async def payments_wallet_hold(request: Request) -> Response:
    return await _proxy_request(request, "payments", "wallets/hold")


@app.post(
    "/api/v1/payments/wallets/commit",
    tags=["Платежи"],
    summary="Подтвердить платёж",
    description="Подтверждает ранее замороженный платёж и переводит средства.",
)
async def payments_wallet_commit(request: Request) -> Response:
    return await _proxy_request(request, "payments", "wallets/commit")


@app.post(
    "/api/v1/payments/wallets/release",
    tags=["Платежи"],
    summary="Разморозить средства",
    description="Снимает заморозку средств и возвращает их на баланс кошелька.",
)
async def payments_wallet_release(request: Request) -> Response:
    return await _proxy_request(request, "payments", "wallets/release")


@app.post(
    "/api/v1/payments/escrow/deposit",
    tags=["Платежи"],
    summary="Внести средства в эскроу",
    description="Переводит средства в эскроу-счёт для обеспечения безопасности сделки.",
)
async def payments_escrow_deposit(request: Request) -> Response:
    return await _proxy_request(request, "payments", "escrow/deposit")


@app.post(
    "/api/v1/payments/escrow/confirm",
    tags=["Платежи"],
    summary="Подтвердить эскроу",
    description="Подтверждает выполнение условий сделки и выпускает средства из эскроу.",
)
async def payments_escrow_confirm(request: Request) -> Response:
    return await _proxy_request(request, "payments", "escrow/confirm")


@app.post(
    "/api/v1/payments/escrow/release",
    tags=["Платежи"],
    summary="Освободить эскроу",
    description="Возвращает средства из эскроу покупателю (при отмене сделки).",
)
async def payments_escrow_release(request: Request) -> Response:
    return await _proxy_request(request, "payments", "escrow/release")


@app.get(
    "/api/v1/payments/transactions",
    tags=["Платежи"],
    summary="История транзакций",
    description="Возвращает историю финансовых операций аутентифицированного пользователя.",
)
async def payments_transactions(request: Request) -> Response:
    return await _proxy_request(request, "payments", "transactions")


# ─── Маршруты: Чат ────────────────────────────────────────────────────────────


@app.post(
    "/api/v1/chat/rooms",
    tags=["Чат"],
    summary="Создать чат-комнату",
    description="Создаёт новую чат-комнату для группы участников закупки.",
    status_code=201,
)
async def chat_rooms_create(request: Request) -> Response:
    return await _proxy_request(request, "chat", "rooms")


@app.get(
    "/api/v1/chat/rooms",
    tags=["Чат"],
    summary="Список чат-комнат",
    description="Возвращает список чат-комнат, доступных текущему пользователю.",
)
async def chat_rooms_list(request: Request) -> Response:
    return await _proxy_request(request, "chat", "rooms")


@app.post(
    "/api/v1/chat/rooms/{room_id}/members/{member_id}",
    tags=["Чат"],
    summary="Добавить участника в чат",
    description="Добавляет пользователя в чат-комнату по его идентификатору.",
)
async def chat_rooms_add_member(room_id: str, member_id: str, request: Request) -> Response:
    return await _proxy_request(request, "chat", f"rooms/{room_id}/members/{member_id}")


@app.get(
    "/api/v1/chat/rooms/{room_id}/messages",
    tags=["Чат"],
    summary="Сообщения в чат-комнате",
    description="Возвращает историю сообщений указанной чат-комнаты с поддержкой пагинации.",
)
async def chat_rooms_messages_list(room_id: str, request: Request) -> Response:
    return await _proxy_request(request, "chat", f"rooms/{room_id}/messages")


@app.post(
    "/api/v1/chat/rooms/{room_id}/messages",
    tags=["Чат"],
    summary="Отправить сообщение",
    description="Отправляет текстовое сообщение в чат-комнату.",
    status_code=201,
)
async def chat_rooms_messages_create(room_id: str, request: Request) -> Response:
    return await _proxy_request(request, "chat", f"rooms/{room_id}/messages")


@app.put(
    "/api/v1/chat/rooms/{room_id}/messages/{message_id}",
    tags=["Чат"],
    summary="Редактировать сообщение",
    description="Изменяет текст ранее отправленного сообщения.",
)
async def chat_rooms_messages_update(room_id: str, message_id: str, request: Request) -> Response:
    return await _proxy_request(request, "chat", f"rooms/{room_id}/messages/{message_id}")


@app.delete(
    "/api/v1/chat/rooms/{room_id}/messages/{message_id}",
    tags=["Чат"],
    summary="Удалить сообщение",
    description="Удаляет сообщение из чат-комнаты (только автор или администратор).",
)
async def chat_rooms_messages_delete(room_id: str, message_id: str, request: Request) -> Response:
    return await _proxy_request(request, "chat", f"rooms/{room_id}/messages/{message_id}")


@app.get(
    "/api/v1/chat/centrifugo/token",
    tags=["Чат"],
    summary="Получить токен Centrifugo",
    description="Выдаёт JWT токен для подключения к Centrifugo WebSocket серверу.",
)
async def chat_centrifugo_token(request: Request) -> Response:
    return await _proxy_request(request, "chat", "centrifugo/token")


# ─── Маршруты: Репутация ──────────────────────────────────────────────────────


@app.post(
    "/api/v1/reputation/reviews",
    tags=["Репутация"],
    summary="Оставить отзыв",
    description="Создаёт отзыв о пользователе после завершения совместной закупки.",
    status_code=201,
)
async def reputation_reviews_create(request: Request) -> Response:
    return await _proxy_request(request, "reputation", "reviews")


@app.get(
    "/api/v1/reputation/reviews/{user_id}",
    tags=["Репутация"],
    summary="Отзывы о пользователе",
    description="Возвращает список всех отзывов о конкретном пользователе.",
)
async def reputation_reviews_get(user_id: str, request: Request) -> Response:
    return await _proxy_request(request, "reputation", f"reviews/{user_id}")


@app.post(
    "/api/v1/reputation/complaints",
    tags=["Репутация"],
    summary="Подать жалобу",
    description="Создаёт жалобу на пользователя с указанием причины и деталей нарушения.",
    status_code=201,
)
async def reputation_complaints_create(request: Request) -> Response:
    return await _proxy_request(request, "reputation", "complaints")


@app.patch(
    "/api/v1/reputation/complaints/{complaint_id}/resolve",
    tags=["Репутация"],
    summary="Разрешить жалобу",
    description="Помечает жалобу как рассмотренную с указанием решения (только для администраторов).",
)
async def reputation_complaints_resolve(complaint_id: str, request: Request) -> Response:
    return await _proxy_request(request, "reputation", f"complaints/{complaint_id}/resolve")


@app.get(
    "/api/v1/reputation/scores/{user_id}",
    tags=["Репутация"],
    summary="Рейтинг пользователя",
    description="Возвращает сводный рейтинг пользователя на основе полученных отзывов.",
)
async def reputation_scores_get(user_id: str, request: Request) -> Response:
    return await _proxy_request(request, "reputation", f"scores/{user_id}")


# ─── Маршруты: Поиск ──────────────────────────────────────────────────────────


@app.post(
    "/api/v1/search/search",
    tags=["Поиск"],
    summary="Полнотекстовый поиск",
    description="Выполняет полнотекстовый поиск по закупкам, товарам и пользователям.",
)
async def search_search(request: Request) -> Response:
    return await _proxy_request(request, "search", "search")


@app.post(
    "/api/v1/search/search/index",
    tags=["Поиск"],
    summary="Индексировать документ",
    description="Добавляет или обновляет документ в поисковом индексе.",
)
async def search_index(request: Request) -> Response:
    return await _proxy_request(request, "search", "search/index")


@app.get(
    "/api/v1/search/filters",
    tags=["Поиск"],
    summary="Получить фильтры поиска",
    description="Возвращает список сохранённых фильтров поиска пользователя.",
)
async def search_filters_list(request: Request) -> Response:
    return await _proxy_request(request, "search", "filters")


@app.post(
    "/api/v1/search/filters",
    tags=["Поиск"],
    summary="Создать фильтр поиска",
    description="Сохраняет новый пользовательский фильтр поиска для быстрого доступа.",
    status_code=201,
)
async def search_filters_create(request: Request) -> Response:
    return await _proxy_request(request, "search", "filters")


@app.delete(
    "/api/v1/search/filters/{filter_id}",
    tags=["Поиск"],
    summary="Удалить фильтр поиска",
    description="Удаляет сохранённый фильтр поиска пользователя.",
)
async def search_filters_delete(filter_id: str, request: Request) -> Response:
    return await _proxy_request(request, "search", f"filters/{filter_id}")


@app.get(
    "/api/v1/search/history",
    tags=["Поиск"],
    summary="История поиска",
    description="Возвращает историю поисковых запросов аутентифицированного пользователя.",
)
async def search_history(request: Request) -> Response:
    return await _proxy_request(request, "search", "history")


# ─── Маршруты: Аналитика ──────────────────────────────────────────────────────


@app.get(
    "/api/v1/analytics/stats/purchases",
    tags=["Аналитика"],
    summary="Статистика закупок",
    description="Возвращает агрегированную статистику по закупкам (только для администраторов).",
)
async def analytics_stats_purchases(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/purchases")


@app.get(
    "/api/v1/analytics/stats/payments",
    tags=["Аналитика"],
    summary="Статистика платежей",
    description="Возвращает агрегированную статистику по платежам и транзакциям.",
)
async def analytics_stats_payments(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/payments")


@app.get(
    "/api/v1/analytics/stats/commissions",
    tags=["Аналитика"],
    summary="Статистика комиссий",
    description="Возвращает статистику по начисленным комиссиям платформы.",
)
async def analytics_stats_commissions(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/commissions")


@app.get(
    "/api/v1/analytics/stats/escrow",
    tags=["Аналитика"],
    summary="Статистика эскроу",
    description="Возвращает статистику по операциям эскроу-счетов.",
)
async def analytics_stats_escrow(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/escrow")


@app.get(
    "/api/v1/analytics/stats/reputation",
    tags=["Аналитика"],
    summary="Статистика репутации",
    description="Возвращает агрегированную статистику по рейтингам и отзывам пользователей.",
)
async def analytics_stats_reputation(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/reputation")


@app.get(
    "/api/v1/analytics/stats/search",
    tags=["Аналитика"],
    summary="Статистика поиска",
    description="Возвращает статистику поисковых запросов и популярных запросов.",
)
async def analytics_stats_search(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/search")


@app.get(
    "/api/v1/analytics/stats/summary",
    tags=["Аналитика"],
    summary="Сводная статистика",
    description="Возвращает общую сводную статистику платформы: пользователи, закупки, платежи.",
)
async def analytics_stats_summary(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "stats/summary")


@app.post(
    "/api/v1/analytics/reports/generate",
    tags=["Аналитика"],
    summary="Сгенерировать отчёт",
    description="Запускает генерацию аналитических отчётов (XLSX/CSV) и загружает их в хранилище.",
)
async def analytics_reports_generate(request: Request) -> Response:
    return await _proxy_request(request, "analytics", "reports/generate")


# ─── Универсальный прокси (для неописанных путей) ─────────────────────────────


@app.api_route(
    "/api/v1/{service_name}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def proxy(service_name: str, path: str, request: Request) -> Response:
    """Универсальный прокси для маршрутизации запросов к микросервисам."""
    return await _proxy_request(request, service_name, path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level=LOG_LEVEL.lower())
