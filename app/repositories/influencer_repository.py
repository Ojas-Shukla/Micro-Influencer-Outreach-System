from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.db.models.influencer import Influencer

def save_influencers(db: Session, influencers: list[dict]) -> dict:
    imported = 0
    duplicates = 0
    seen_in_file = set()

    try:
        for data in influencers:
            platform = data["platform"]
            username = data["username"]
            platform_user_id = data.get("platform_user_id")

            # Prevent duplicates within this import
            key = (platform, platform_user_id or username)

            if key in seen_in_file:
                duplicates += 1
                continue

            seen_in_file.add(key)

            conditions = [
                Influencer.username == username
            ]

            if platform_user_id:
                conditions.append(
                    Influencer.platform_user_id == platform_user_id
                )

            existing = db.scalar(
                select(Influencer.id).where(
                    Influencer.platform == platform,
                    or_(*conditions)
                )
            )

            if existing is not None:
                duplicates += 1
                continue

            db.add(Influencer(**data))
            imported += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "imported": imported,
        "duplicates": duplicates
    }