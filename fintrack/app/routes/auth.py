"""Auth routes — register, login, logout."""

from fastapi import APIRouter, Request, Form, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import db_cursor
from app.utils.auth import hash_password, verify_password, create_token, optional_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = optional_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email:    str = Form(...),
    password: str = Form(...),
    confirm:  str = Form(...),
):
    errors = []
    if len(username) < 3:
        errors.append("Username must be at least 3 characters.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "errors": errors, "username": username, "email": email
        })

    try:
        with db_cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email.lower(), hash_password(password))
            )
        return RedirectResponse("/auth/login?registered=1", status_code=303)
    except Exception:
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "errors": ["Username or email already taken."],
            "username": username, "email": email,
        })


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, registered: str = ""):
    user = optional_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "registered": registered == "1",
    })


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    with db_cursor() as cur:
        cur.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
        user = cur.fetchone()

    if not user or not verify_password(password, user["password"]):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid username or password.",
            "username": username,
        })

    token = create_token(user["id"], user["username"])
    resp  = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("token", token, httponly=True, max_age=60*60*24*7, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/auth/login", status_code=303)
    resp.delete_cookie("token")
    return resp
