from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from logging_setup import logger
from models import CategoryModel, LogEntryModel, ProductModel, UserModel, UserRole
from security import hash_password


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


class LogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: Optional[int], action: str, details: str = ""):
        entry = LogEntryModel(user_id=user_id, action=action, details=details)
        self.db.add(entry)
        self.db.commit()
        logger.info("user=%s action=%s details=%s", user_id, action, details)
