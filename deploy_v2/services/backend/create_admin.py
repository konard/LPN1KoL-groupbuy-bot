"""Create the first admin user. Run once after first startup.

Usage inside container:
  docker compose exec backend python create_admin.py admin admin@example.com password123
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.main import SessionLocal, UserModel, hash_password


def main():
    if len(sys.argv) != 4:
        print("Usage: python create_admin.py <username> <email> <password>")
        sys.exit(1)

    username, email, password = sys.argv[1], sys.argv[2], sys.argv[3]
    db = SessionLocal()
    try:
        existing = db.query(UserModel).filter(UserModel.username == username).first()
        if existing:
            existing.is_admin = True
            db.commit()
            print(f"User '{username}' already exists. Granted admin.")
            return
        user = UserModel(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
