import argparse
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
    parser = argparse.ArgumentParser(
        description="Discover YouTube influencer channels"
    )

    parser.add_argument(
        "--query",
        default="fitness creators India",
        help="YouTube channel discovery search query"
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=2,
        help="Number of search pages (1 to 5)"
    )

    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    print(f"Search query: {args.query}")
    print(f"Search pages: {args.pages}")

    channel_ids = search_channels(
        query=args.query,
        max_pages=args.pages
    )

    print(f"\nChannel IDs discovered: {len(channel_ids)}")

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

        print("\nDiscovery report:")
        print(json.dumps({
            "search_query": args.query,
            "pages_requested": args.pages,
            "channel_ids_discovered": len(channel_ids),
            "channel_details_received": len(channels),
            "valid_records": len(influencers),
            **result
        }, indent=4))

    finally:
        db.close()


if __name__ == "__main__":
    main()