import os
from typing import Optional

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
async def index(
    request: Request,
    balance_msg: Optional[str] = None,
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    users = await api_get("/users?limit=200", admin_token) or []
    health = await api_get("/health", admin_token) or {}
    return templates.TemplateResponse("index.html", {
        "request": request,
        "users": users,
        "health": health,
        "balance_msg": balance_msg,
    })


@app.post("/users/{user_id}/toggle-active")
async def toggle_active(user_id: int, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    user = await api_get(f"/users/{user_id}", admin_token)
    if user:
        await api_patch(f"/users/{user_id}", admin_token, {"is_active": not user["is_active"]})
    return RedirectResponse("/", status_code=302)


@app.post("/users/{user_id}/adjust-balance")
async def adjust_balance(
    user_id: int,
    amount: float = Form(...),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    await api_post(f"/users/{user_id}/balance", admin_token, {"amount": amount})
    return RedirectResponse("/?balance_msg=Balance+adjusted", status_code=302)


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
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "step": "phone",
        "phone": "",
        "email_hint": "",
    })


@app.post("/login")
async def login(
    request: Request,
    response: Response,
    phone: str = Form(...),
    password: str = Form(...),
):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.post("/auth/login", json={"phone": phone, "password": password})
    if r.status_code != 200:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid phone number or password.",
            "step": "phone",
            "phone": "",
            "email_hint": "",
        })
    data = r.json()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "step": "code",
        "phone": phone,
        "email_hint": data.get("email_hint", ""),
    })


@app.post("/login/verify")
async def login_verify(
    request: Request,
    response: Response,
    phone: str = Form(...),
    code: str = Form(...),
):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.post("/auth/verify-code", json={"phone": phone, "code": code})
    if r.status_code != 200:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid or expired verification code.",
            "step": "code",
            "phone": phone,
            "email_hint": "",
        })
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


# ── Complaints ────────────────────────────────────────────────────────────────
@app.get("/complaints", response_class=HTMLResponse)
async def complaints_page(
    request: Request,
    status: Optional[str] = None,
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    path = "/complaints"
    if status:
        path += f"?status={status}"
    complaints = await api_get(path, admin_token) or []
    return templates.TemplateResponse("complaints.html", {
        "request": request,
        "complaints": complaints,
        "current_filter": status or "",
    })


@app.post("/complaints/{cid}/update")
async def update_complaint_view(
    cid: int,
    status: str = Form(...),
    resolution: str = Form(""),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    await api_patch(f"/complaints/{cid}", admin_token, {"status": status, "resolution": resolution})
    return RedirectResponse("/complaints", status_code=302)


# ── Analytics ─────────────────────────────────────────────────────────────────
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    a = await api_get("/admin/analytics", admin_token) or {
        "window_days": 30,
        "new_users_30d": 0,
        "new_procurements_30d": 0,
        "status_breakdown": {},
        "payments_by_type": {},
        "top_cities": [],
        "top_participants": [],
        "open_complaints": 0,
        "generated_at": "",
    }
    return templates.TemplateResponse("analytics.html", {"request": request, "a": a})


# ── Broadcasts ────────────────────────────────────────────────────────────────
@app.get("/broadcasts", response_class=HTMLResponse)
async def broadcasts_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    return templates.TemplateResponse("broadcasts.html", {"request": request, "sent": None})


@app.post("/broadcasts", response_class=HTMLResponse)
async def send_broadcast(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    link: str = Form(""),
    kind: str = Form("system"),
    admin_token: str | None = Cookie(default=None),
):
    if not admin_token:
        return RedirectResponse("/login")
    result = await api_post(
        "/admin/broadcast",
        admin_token,
        {"title": title, "body": body, "link": link, "kind": kind},
    ) or {"sent": 0}
    return templates.TemplateResponse(
        "broadcasts.html",
        {"request": request, "sent": result.get("sent", 0)},
    )


# ── Activity log ──────────────────────────────────────────────────────────────
@app.get("/activity-log", response_class=HTMLResponse)
async def activity_log_page(request: Request, admin_token: str | None = Cookie(default=None)):
    if not admin_token:
        return RedirectResponse("/login")
    rows = await api_get("/admin/activity-log?limit=200", admin_token) or []
    return templates.TemplateResponse("activity_log.html", {"request": request, "rows": rows})
