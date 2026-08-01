"""Grant or revoke a role.

    python -m app.promote --list
    python -m app.promote you@example.com admin
    python -m app.promote you@example.com user      # demote

ponytail: a command, not a startup env var. `ADMIN_EMAILS` would silently re-promote
anyone you had deliberately demoted on the next restart; running this leaves a decision
where someone made it. Registration has no way to ask for a role, so without this the
admin endpoints are unreachable except by editing the database by hand.
"""

import sys

from sqlalchemy import select

from .db import SessionLocal
from .models import ROLES, User


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    with SessionLocal() as db:
        if argv[0] == "--list":
            users = db.scalars(select(User).order_by(User.id)).all()
            if not users:
                print("No users yet.")
            for user in users:
                print(f"{user.id:>4}  {user.role:<6}  {user.email}")
            return 0

        email = argv[0].strip().lower()
        role = (argv[1] if len(argv) > 1 else "admin").strip().lower()

        if role not in ROLES:
            print(f"Unknown role {role!r}. Valid roles: {', '.join(ROLES)}", file=sys.stderr)
            return 2

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email!r}. Register first, then run this.", file=sys.stderr)
            return 1

        if user.role == role:
            print(f"{email} is already {role}.")
            return 0

        was, user.role = user.role, role
        db.commit()
        print(f"{email}: {was} -> {role}")
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via main() in tests
    raise SystemExit(main(sys.argv[1:]))
