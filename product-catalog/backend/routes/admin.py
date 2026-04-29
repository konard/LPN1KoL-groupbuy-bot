from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models import UserModel, UserRole
from repositories import LogRepository, UserRepository
from schemas import PasswordChange, UserCreate, UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=List[UserOut])
def admin_list_users(
    db: Session = Depends(get_db),
    _=Depends(require_role(UserRole.admin)),
):
    return UserRepository(db).list_all()


@router.post("/users", response_model=UserOut, status_code=201)
def admin_create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.admin)),
):
    repo = UserRepository(db)
    if repo.get_by_username(data.username):
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")
    new_user = repo.create(data.username, data.password, data.role)
    LogRepository(db).create(user.id, "admin_create_user", f"username={data.username} role={data.role}")
    return new_user


@router.patch("/users/{user_id}/block", response_model=UserOut)
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
    LogRepository(db).create(admin.id, "admin_toggle_block", f"user_id={user_id} is_active={not target.is_active}")
    db.refresh(target)
    return target


@router.delete("/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_role(UserRole.admin)),
):
    UserRepository(db).delete(user_id)
    LogRepository(db).create(admin.id, "admin_delete_user", f"user_id={user_id}")


@router.patch("/users/{user_id}/password", status_code=204)
def admin_change_password(
    user_id: int,
    data: PasswordChange,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_role(UserRole.admin)),
):
    UserRepository(db).update_password(user_id, data.new_password)
    LogRepository(db).create(admin.id, "admin_change_password", f"user_id={user_id}")
