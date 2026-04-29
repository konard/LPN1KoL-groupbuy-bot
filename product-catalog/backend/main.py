import os
import logging
import logging.handlers
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import httpx
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime,
    Float, Text, ForeignKey, Enum as SAEnum, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
import enum

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./product_catalog.db")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-change-in-prod-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:80",
).split(",")
NBRB_API_URL = "https://api.nbrb.by/exrates/rates/431?parammode=1"  # USD rate

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("product_catalog")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = logging.handlers.RotatingFileHandler("logs/app.log", maxBytes=5_000_000, backupCount=3)
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_sh)

# ── DB ────────────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Enums ─────────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    simple_user = "simple_user"
    advanced_user = "advanced_user"
    admin = "admin"


# ── Models ────────────────────────────────────────────────────────────────────
class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.simple_user, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CategoryModel(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    products = relationship(
        "ProductModel", back_populates="category", cascade="all, delete-orphan"
    )


class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    price_rub = Column(Float, nullable=False)
    general_note = Column(Text, default="")
    special_note = Column(Text, default="")
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    category = relationship("CategoryModel", back_populates="products")


class LogEntryModel(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(200), nullable=False)
    details = Column(Text, default="")


Base.metadata.create_all(bind=engine)

# ── Auth helpers ──────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_token_payload(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    payload = get_token_payload(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден или неактивен")
    return user


def require_role(*roles: UserRole):
    def _dep(user: UserModel = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user
    return _dep


def log_action(db: Session, user_id: Optional[int], action: str, details: str = ""):
    entry = LogEntryModel(user_id=user_id, action=action, details=details)
    db.add(entry)
    db.commit()
    logger.info("user=%s action=%s details=%s", user_id, action, details)


# ── Repository layer ──────────────────────────────────────────────────────────
class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> List[CategoryModel]:
        return self.db.query(CategoryModel).all()

    def get(self, cat_id: int) -> Optional[CategoryModel]:
        return self.db.query(CategoryModel).filter(CategoryModel.id == cat_id).first()

    def get_by_name(self, name: str) -> Optional[CategoryModel]:
        return self.db.query(CategoryModel).filter(CategoryModel.name == name).first()

    def create(self, name: str) -> CategoryModel:
        cat = CategoryModel(name=name)
        self.db.add(cat)
        self.db.commit()
        self.db.refresh(cat)
        return cat

    def update(self, cat_id: int, name: str) -> CategoryModel:
        cat = self.get(cat_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Категория не найдена")
        cat.name = name
        self.db.commit()
        self.db.refresh(cat)
        return cat

    def delete(self, cat_id: int):
        cat = self.get(cat_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Категория не найдена")
        self.db.delete(cat)
        self.db.commit()


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(
        self,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProductModel]:
        q = self.db.query(ProductModel)
        if search:
            q = q.filter(ProductModel.name.ilike(f"%{search}%"))
        if category_id:
            q = q.filter(ProductModel.category_id == category_id)
        return q.offset(skip).limit(limit).all()

    def get(self, product_id: int) -> Optional[ProductModel]:
        return self.db.query(ProductModel).filter(ProductModel.id == product_id).first()

    def create(self, data: dict) -> ProductModel:
        product = ProductModel(**data)
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update(self, product_id: int, data: dict) -> ProductModel:
        product = self.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Продукт не найден")
        for k, v in data.items():
            setattr(product, k, v)
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product_id: int):
        product = self.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Продукт не найден")
        self.db.delete(product)
        self.db.commit()


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> List[UserModel]:
        return self.db.query(UserModel).all()

    def get(self, user_id: int) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.username == username).first()

    def create(self, username: str, password: str, role: UserRole) -> UserModel:
        user = UserModel(
            username=username,
            hashed_password=hash_password(password),
            role=role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user_id: int, new_password: str):
        user = self.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.hashed_password = hash_password(new_password)
        self.db.commit()

    def set_active(self, user_id: int, is_active: bool):
        user = self.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.is_active = is_active
        self.db.commit()

    def delete(self, user_id: int):
        user = self.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        self.db.delete(user)
        self.db.commit()


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryIn(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class ProductIn(BaseModel):
    name: str
    description: str = ""
    price_rub: float
    general_note: str = ""
    special_note: str = ""
    category_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_rub: Optional[float] = None
    general_note: Optional[str] = None
    special_note: Optional[str] = None
    category_id: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    price_rub: float
    general_note: str
    special_note: str
    category_id: int
    category_name: str

    model_config = {"from_attributes": True}


class ProductOutSimple(BaseModel):
    id: int
    name: str
    description: str
    price_rub: float
    general_note: str
    category_id: int
    category_name: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole


class PasswordChange(BaseModel):
    new_password: str


class UsdConversion(BaseModel):
    price_rub: float
    price_usd: float
    rate: float


# ── Helpers ───────────────────────────────────────────────────────────────────
def product_out(p: ProductModel, include_special: bool = True):
    base = {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "price_rub": p.price_rub,
        "general_note": p.general_note or "",
        "category_id": p.category_id,
        "category_name": p.category.name if p.category else "",
    }
    if include_special:
        base["special_note"] = p.special_note or ""
        return ProductOut(**base)
    else:
        return ProductOutSimple(**base)


# ── Seed data ─────────────────────────────────────────────────────────────────
def seed_data(db: Session):
    repo_cat = CategoryRepository(db)
    repo_prod = ProductRepository(db)
    repo_user = UserRepository(db)

    # Create default admin
    if not repo_user.get_by_username("admin"):
        repo_user.create("admin", "admin123", UserRole.admin)
        logger.info("Created default admin user (username=admin, password=admin123)")

    if not repo_user.get_by_username("advanced"):
        repo_user.create("advanced", "advanced123", UserRole.advanced_user)

    if not repo_user.get_by_username("user"):
        repo_user.create("user", "user123", UserRole.simple_user)

    # Seed categories and products
    seed_products = [
        ("Еда", [
            ("Селедка", "Селедка соленая", 10.0, "Акция", "Пересоленая"),
            ("Тушенка", "Тушенка говяжья", 20.0, "Вкусная", "Жилы"),
        ]),
        ("Вкусности", [
            ("Сгущенка", "В банках", 30.0, "С ключом", "Вкусная"),
        ]),
        ("Вода", [
            ("Квас", "В бутылках", 15.0, "Вятский", "Теплый"),
        ]),
    ]

    for cat_name, products in seed_products:
        cat = repo_cat.get_by_name(cat_name)
        if not cat:
            cat = repo_cat.create(cat_name)
        for name, desc, price, gnote, snote in products:
            existing = db.query(ProductModel).filter(
                ProductModel.name == name, ProductModel.category_id == cat.id
            ).first()
            if not existing:
                repo_prod.create({
                    "name": name,
                    "description": desc,
                    "price_rub": price,
                    "general_note": gnote,
                    "special_note": snote,
                    "category_id": cat.id,
                })


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Product Catalog API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_username(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверные учётные данные")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    access = create_token({"sub": str(user.id), "role": user.role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh = create_token({"sub": str(user.id), "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    log_action(db, user.id, "login", f"username={user.username}")
    return LoginResponse(access_token=access, refresh_token=refresh, role=user.role)


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = get_token_payload(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Токен не является refresh-токеном")
    user_id = payload.get("sub")
    user = db.query(UserModel).filter(UserModel.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден или неактивен")
    access = create_token({"sub": str(user.id), "role": user.role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return TokenResponse(access_token=access)


@app.get("/auth/me", response_model=UserOut)
def me(user: UserModel = Depends(get_current_user)):
    return user


# ── Category routes ───────────────────────────────────────────────────────────
@app.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return CategoryRepository(db).list_all()


@app.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    data: CategoryIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    repo = CategoryRepository(db)
    if repo.get_by_name(data.name):
        raise HTTPException(status_code=400, detail="Категория с таким именем уже существует")
    cat = repo.create(data.name)
    log_action(db, user.id, "create_category", f"name={data.name}")
    return cat


@app.put("/categories/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    data: CategoryIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    repo = CategoryRepository(db)
    existing = repo.get_by_name(data.name)
    if existing and existing.id != cat_id:
        raise HTTPException(status_code=400, detail="Категория с таким именем уже существует")
    cat = repo.update(cat_id, data.name)
    log_action(db, user.id, "update_category", f"id={cat_id} name={data.name}")
    return cat


@app.delete("/categories/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    CategoryRepository(db).delete(cat_id)
    log_action(db, user.id, "delete_category", f"id={cat_id}")


# ── Product routes ────────────────────────────────────────────────────────────
@app.get("/products")
def list_products(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    products = ProductRepository(db).list_all(search=search, category_id=category_id, skip=skip, limit=limit)
    include_special = user.role in (UserRole.advanced_user, UserRole.admin)
    return [product_out(p, include_special) for p in products]


@app.post("/products", status_code=201)
def create_product(
    data: ProductIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.simple_user, UserRole.advanced_user, UserRole.admin)),
):
    cat = CategoryRepository(db).get(data.category_id)
    if not cat:
        raise HTTPException(status_code=400, detail="Категория не найдена")
    product = ProductRepository(db).create(data.model_dump())
    log_action(db, user.id, "create_product", f"name={data.name}")
    return product_out(product, include_special=True)


@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    product = ProductRepository(db).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    include_special = user.role in (UserRole.advanced_user, UserRole.admin)
    return product_out(product, include_special)


@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.simple_user, UserRole.advanced_user, UserRole.admin)),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if "category_id" in updates:
        cat = CategoryRepository(db).get(updates["category_id"])
        if not cat:
            raise HTTPException(status_code=400, detail="Категория не найдена")
    product = ProductRepository(db).update(product_id, updates)
    log_action(db, user.id, "update_product", f"id={product_id}")
    include_special = user.role in (UserRole.advanced_user, UserRole.admin)
    return product_out(product, include_special)


@app.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    ProductRepository(db).delete(product_id)
    log_action(db, user.id, "delete_product", f"id={product_id}")


# ── Currency conversion ───────────────────────────────────────────────────────
@app.get("/convert-usd", response_model=UsdConversion)
async def convert_usd(
    amount: float = Query(..., description="Amount in BYN rubles"),
    _=Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(NBRB_API_URL)
            resp.raise_for_status()
            data = resp.json()
            rate = data["Cur_OfficialRate"] / data["Cur_Scale"]
    except Exception as e:
        logger.error("NBRB API error: %s", e)
        raise HTTPException(status_code=502, detail="Не удалось получить курс валюты от НБРБ")
    price_usd = amount / rate
    return UsdConversion(price_rub=amount, price_usd=round(price_usd, 4), rate=round(rate, 4))


# ── Admin: user management ────────────────────────────────────────────────────
@app.get("/admin/users", response_model=List[UserOut])
def admin_list_users(
    db: Session = Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    return UserRepository(db).list_all()


@app.post("/admin/users", response_model=UserOut, status_code=201)
def admin_create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.admin)),
):
    repo = UserRepository(db)
    if repo.get_by_username(data.username):
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    new_user = repo.create(data.username, data.password, data.role)
    log_action(db, user.id, "admin_create_user", f"username={data.username} role={data.role}")
    return new_user


@app.patch("/admin/users/{user_id}/block", response_model=UserOut)
def admin_block_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_role(UserRole.admin)),
):
    repo = UserRepository(db)
    target = repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    repo.set_active(user_id, not target.is_active)
    log_action(db, admin.id, "admin_toggle_block", f"user_id={user_id} is_active={not target.is_active}")
    db.refresh(target)
    return target


@app.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_role(UserRole.admin)),
):
    UserRepository(db).delete(user_id)
    log_action(db, admin.id, "admin_delete_user", f"user_id={user_id}")


@app.patch("/admin/users/{user_id}/password", status_code=204)
def admin_change_password(
    user_id: int,
    data: PasswordChange,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_role(UserRole.admin)),
):
    UserRepository(db).update_password(user_id, data.new_password)
    log_action(db, admin.id, "admin_change_password", f"user_id={user_id}")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
