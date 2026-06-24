import sys
import os
from sqlalchemy import text, select
from werkzeug.security import generate_password_hash

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server"))
from database import get_engine, get_db
from models import User

def check_and_create_user():
    engine = get_engine()
    try:
        with get_db() as db:
            users = db.scalars(select(User)).all()
            print(f"Existing users in DB: {len(users)}")
            for u in users:
                print(f" - ID: {u.id} | Username: {u.username} | Active: {u.is_active}")
            
            if not users:
                print("No users found. Creating user 'admin' with password 'admin123'...")
                admin = User(
                    username="admin",
                    password_hash=generate_password_hash("admin123"),
                    is_active=True,
                    is_admin=True
                )
                db.add(admin)
                db.flush()
                print("Admin user created successfully!")
    except Exception as e:
        print(f"Error checking/creating users: {e}")

if __name__ == "__main__":
    check_and_create_user()
