import asyncio
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import RecordStatus, UserRole
from app.models.organization import Organization
from app.models.user import User


async def seed() -> None:
    async with SessionLocal() as db:
        org = await db.scalar(select(Organization).where(Organization.slug == "demo-law"))
        now = datetime.now(timezone.utc)

        if not org:
            org = Organization(
                name="Demo Law Firm",
                slug="demo-law",
                status=RecordStatus.active,
                created_at=now,
                updated_at=now,
            )
            db.add(org)
            await db.flush()

        users = [
            ("Ava Partner", "partner@vilo.dev", UserRole.partner),
            ("Noah Admin", "admin@vilo.dev", UserRole.admin),
            ("Liam Lawyer", "lawyer@vilo.dev", UserRole.lawyer),
            ("Mia Paralegal", "paralegal@vilo.dev", UserRole.paralegal),
            ("Ethan Client", "client@vilo.dev", UserRole.client),
        ]

        for name, email, role in users:
            exists = await db.scalar(select(User).where(User.email == email))
            if exists:
                continue
            db.add(
                User(
                    organization_id=org.id,
                    name=name,
                    email=email,
                    hashed_password=hash_password("Password123!"),
                    role=role,
                    status=RecordStatus.active,
                    created_at=now,
                    updated_at=now,
                )
            )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
