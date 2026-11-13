import json

from sqlalchemy import func

from app.db.session import SessionLocal
from app.db.models.influencer import Influencer


def main():
    db = SessionLocal()

    try:
        youtube_query = db.query(Influencer).filter(
            Influencer.platform == "youtube",
            Influencer.source == "youtube_data_api_v3"
        )

        total = youtube_query.count()

        with_followers = youtube_query.filter(
            Influencer.followers_count.isnot(None)
        ).count()

        with_description = youtube_query.filter(
            Influencer.bio.isnot(None),
            Influencer.bio != ""
        ).count()

        with_channel_id = youtube_query.filter(
            Influencer.platform_user_id.isnot(None)
        ).count()

        unique_channel_ids = db.query(
            func.count(
                func.distinct(Influencer.platform_user_id)
            )
        ).filter(
            Influencer.platform == "youtube",
            Influencer.platform_user_id.isnot(None)
        ).scalar()

        report = {
            "total_api_discovered_profiles": total,
            "profiles_with_subscriber_counts": with_followers,
            "profiles_with_descriptions": with_description,
            "profiles_with_channel_ids": with_channel_id,
            "unique_channel_ids": unique_channel_ids,
            "discovery_target": 50,
            "discovery_target_reached": total >= 50,
        }

        print(json.dumps(report, indent=4))

    finally:
        db.close()


if __name__ == "__main__":
    main()