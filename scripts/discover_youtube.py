import json

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db import models

from app.repositories.influencer_repository import save_influencers
from app.services.discovery.youtube_client import (
    search_channels,
    fetch_channel_details,
    normalize_channel
)

def main():
    search_query = input("Enter YouTube search query: ") 

    Base.metadata.create_all(bind=engine)

    print(f"Searching YouTube for: {search_query}")

    channel_ids = search_channels(
        query=search_query,
        max_pages=1
    )

    print(f"Channel IDs discovered: {len(channel_ids)}")

    channels = fetch_channel_details(channel_ids)

    influencers = [
        normalize_channel(channel)
        for channel in channels
    ]

    influencers = [
        influencer
        for influencer in influencers
        if influencer is not None
    ]

    db = SessionLocal()

    try:
        result = save_influencers(db, influencers)

        print("\nImport result:")
        print(json.dumps({
            "discovered": len(channel_ids),
            "details_fetched": len(channels),
            **result
        }, indent=4))

    finally:
        db.close()


if __name__ == "__main__":
    main()