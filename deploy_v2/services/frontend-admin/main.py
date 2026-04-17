import os
import httpx
from fastapi import FastAPI, Request, Form, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app = FastAPI(title="GroupBuy Admin Panel")
templates = Jinja2Templates(directory="templates")


# ── Auth helpers ──────────────────────────────────────────────────────────────
async def api_get(path: str, token: str) -> dict | list | None:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            return r.json()
    return None


async def api_post(path: str, token: str, data: dict) -> dict | None:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.post(path, json=data, headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (200, 201):
            return r.json()
    return None


async def api_patch(path: str, token: str, data: dict) -> bool:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.patch(path, json=data, headers={"Authorization": f"Bearer {token}"})
        return r.status_code == 200


async def api_delete(path: str, token: str) -> bool:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.delete(path, headers={"Authorization": f"Bearer {token}"})
        return r.status_code in (200, 204)


def require_token(admin_token: str | None) -> str | None:
    if not admin_token:
        return None
    return admin_token


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    health = await api_get("/health", admin_token) or {}
    stats_raw = await api_get("/admin/stats", admin_token) or {}
    recent_procurements = await api_get("/procurements?limit=5", admin_token) or []
    recent_users = await api_get("/users?limit=5", admin_token) or []
    stats = {
        "users": stats_raw.get("total_users", len(recent_users)),
        "active_procurements": stats_raw.get("active_procurements", 0),
        "total_procurements": stats_raw.get("total_procurements", 0),
        "total_payments": stats_raw.get("total_payments", 0),
    }
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "health": health,
        "stats": stats,
        "recent_procurements": recent_procurements[:5],
        "recent_users": recent_users[:5],
    })


# ── Users ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    users = await api_get("/users?limit=200", admin_token) or []
    health = await api_get("/health", admin_token) or {}
    return templates.TemplateResponse("index.html", {
        "request": request,
        "users": users,
        "health": health,
    })


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


# ── Procurements ──────────────────────────────────────────────────────────────
@app.get("/procurements", response_class=HTMLResponse)
async def procurements_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    procurements = await api_get("/procurements?limit=200", admin_token) or []
    categories = await api_get("/categories", admin_token) or []
    return templates.TemplateResponse("procurements.html", {
        "request": request,
        "procurements": procurements,
        "categories": categories,
    })


@app.post("/procurements/{proc_id}/status")
async def set_procurement_status(
    proc_id: int,
    new_status: str = Form(...),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    await api_patch(f"/procurements/{proc_id}", admin_token, {"status": new_status})
    return RedirectResponse("/procurements", status_code=302)


@app.post("/procurements/{proc_id}/delete")
async def delete_procurement(proc_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    await api_delete(f"/procurements/{proc_id}", admin_token)
    return RedirectResponse("/procurements", status_code=302)


# ── Categories ────────────────────────────────────────────────────────────────
@app.get("/categories", response_class=HTMLResponse)
async def categories_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    categories = await api_get("/categories", admin_token) or []
    return templates.TemplateResponse("categories.html", {
        "request": request,
        "categories": categories,
    })


@app.post("/categories/create")
async def create_category(
    name: str = Form(...),
    description: str = Form(""),
    icon: str = Form(""),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    await api_post("/categories", admin_token, {"name": name, "description": description, "icon": icon})
    return RedirectResponse("/categories", status_code=302)


@app.post("/categories/{cat_id}/delete")
async def delete_category(cat_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    await api_delete(f"/categories/{cat_id}", admin_token)
    return RedirectResponse("/categories", status_code=302)


# ── Payments ──────────────────────────────────────────────────────────────────
@app.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    payments_raw = await api_get("/payments?limit=200", admin_token) or []
    users_raw = await api_get("/users?limit=200", admin_token) or []
    user_map = {u["id"]: u["username"] for u in users_raw}
    payments = [{**p, "username": user_map.get(p["user_id"], str(p["user_id"]))} for p in payments_raw]
    return templates.TemplateResponse("payments.html", {
        "request": request,
        "payments": payments,
    })


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.post("/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        resp = RedirectResponse("/login?error=1", status_code=302)
        return resp
    token = r.json()["access_token"]
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie("admin_token", token, httponly=True, samesite="lax")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("admin_token")
    return resp


@app.get("/health")
async def health():
    return {"status": "ok"}
