import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./product_catalog.db")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-change-in-prod-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:80",
).split(",")
NBRB_API_URL = "https://api.nbrb.by/exrates/rates/431?parammode=1"
