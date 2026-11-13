import json
import sys

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db import models
from app.services.discovery.csv_importer import import_csv


def main():
    file_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/raw/influencers.csv"
    )

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        result = import_csv(file_path, db)
        print(json.dumps(result, indent=4))
    finally:
        db.close()


if __name__ == "__main__":
    main()