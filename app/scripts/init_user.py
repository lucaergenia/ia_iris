import argparse
from datetime import datetime
from app.database.database import db
from app.auth.security import hash_password


def main():
    p = argparse.ArgumentParser(description="Crear usuario inicial")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--name", default="Admin")
    p.add_argument("--role", default="superuser")
    args = p.parse_args()

    email = args.email.lower().strip()
    if db.users.find_one({"email": email}):
        print(f"Ya existe un usuario con email {email}")
        return

    doc = {
        "email": email,
        "name": args.name,
        "password_hash": hash_password(args.password),
        "role": args.role,
        "active": True,
        "created_at": datetime.utcnow(),
    }
    db.users.insert_one(doc)
    print(f"Usuario creado: {email} ({args.role})")


if __name__ == "__main__":
    main()

