import os
import httpx
from fastapi import FastAPI, Request, Form, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app = FastAPI(title="GroupBuy Admin Panel")
templates = Jinja2Templates(directory="templates")


# ── Auth helpers ──────────────────────────────────────────────────────────────
async def get_token(token: str | None) -> str | None:
    return token


async def api_get(path: str, token: str) -> dict | list | None:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            return r.json()
    return None


async def api_patch(path: str, token: str, data: dict) -> bool:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.patch(path, json=data, headers={"Authorization": f"Bearer {token}"})
        return r.status_code == 200


async def api_delete(path: str, token: str) -> bool:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.delete(path, headers={"Authorization": f"Bearer {token}"})
        return r.status_code == 204


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    users = await api_get("/users", admin_token) or []
    health = await api_get("/health", admin_token) or {}
    return templates.TemplateResponse("index.html", {
        "request": request,
        "users": users,
        "health": health,
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.post("/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        # Re-render with error — need a Request object; redirect instead
        resp = RedirectResponse("/login?error=1", status_code=302)
        return resp
    token = r.json()["access_token"]
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("admin_token", token, httponly=True, samesite="lax")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("admin_token")
    return resp


@app.post("/users/{user_id}/toggle-active")
async def toggle_active(user_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    user = await api_get(f"/users/{user_id}", admin_token)
    if user:
        await api_patch(f"/users/{user_id}", admin_token, {"is_active": not user["is_active"]})
    return RedirectResponse("/", status_code=302)


@app.post("/users/{user_id}/delete")
async def delete_user(user_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    await api_delete(f"/users/{user_id}", admin_token)
    return RedirectResponse("/", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok"}
