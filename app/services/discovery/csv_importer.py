import csv
from io import StringIO
from pathlib import Path

from app.repositories.influencer_repository import save_influencers

def parse_optional_int(value, field_name):
    if value is None or not value.strip():
        return None

    try:
        number = int(value)
        if number < 0:
            raise ValueError
        return number
    except ValueError:
        raise ValueError(f"{field_name} must be a non-negative integer")


def parse_optional_float(value, field_name):
    if value is None or not value.strip():
        return None

    try:
        number = float(value)
        if number < 0:
            raise ValueError
        return number
    except ValueError:
        raise ValueError(f"{field_name} must be a non-negative number")


def parse_optional_bool(value, field_name):
    if value is None or not value.strip():
        return False

    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise ValueError(f"{field_name} must be true or false")


def normalize_row(row):
    platform = (row.get("platform") or "").strip().lower()
    username = (row.get("username") or "").strip().lstrip("@").lower()

    if not platform:
        raise ValueError("Platform is required")

    if not username:
        raise ValueError("Username is required")

    email = (row.get("email") or "").strip().lower() or None

    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise ValueError("Email format is invalid")

    profile_url = (row.get("profile_url") or "").strip() or None

    if profile_url and not profile_url.startswith(("https://", "http://")):
        raise ValueError("Profile URL must start with http:// or https://")

    engagement_rate = parse_optional_float(
        row.get("engagement_rate"),
        "engagement_rate"
    )

    if engagement_rate is not None and engagement_rate > 100:
        raise ValueError("engagement_rate cannot exceed 100 percent")

    return {
        "platform": platform,
        "username": username,
        "display_name": (row.get("display_name") or "").strip() or None,
        "profile_url": profile_url,
        "niche": (row.get("niche") or "").strip() or None,
        "bio": (row.get("bio") or "").strip() or None,
        "followers_count": parse_optional_int(
            row.get("followers_count"), "followers_count"
        ),
        "following_count": parse_optional_int(
            row.get("following_count"), "following_count"
        ),
        "posts_count": parse_optional_int(
            row.get("posts_count"), "posts_count"
        ),
        "avg_likes": parse_optional_float(
            row.get("avg_likes"), "avg_likes"
        ),
        "avg_comments": parse_optional_float(
            row.get("avg_comments"), "avg_comments"
        ),
        "engagement_rate": engagement_rate,
        "email": email,
        "location": (row.get("location") or "").strip() or None,
        "is_verified": parse_optional_bool(
            row.get("is_verified"), "is_verified"
        ),
        "source": (row.get("source") or "csv_import").strip(),
    }


def import_csv(file_path: str, db):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    return import_csv_content(path.read_bytes(), db)


def import_csv_content(content: bytes, db):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 encoding") from error

    valid_records = []
    errors = []

    reader = csv.DictReader(StringIO(text))

    required_columns = {"platform", "username"}

    if not reader.fieldnames or not required_columns.issubset(
        set(reader.fieldnames)
    ):
        raise ValueError("CSV must contain platform and username columns")

    total_rows = 0
    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            valid_records.append(normalize_row(row))
        except ValueError as error:
            errors.append({
                "row": row_number,
                "error": str(error)
            })

    result = save_influencers(db, valid_records)

    return {
        "total_rows": total_rows,
        "imported": result["imported"],
        "duplicates": result["duplicates"],
        "invalid": len(errors),
        "errors": errors
    }