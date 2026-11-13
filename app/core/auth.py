import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_dashboard_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Require the configured bearer token on dashboard and data API routes."""
    expected_token = get_settings().dashboard_api_token
    if len(expected_token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API access is disabled until DASHBOARD_API_TOKEN is "
                "configured with at least 32 characters."
            ),
        )

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not hmac.compare_digest(supplied_token, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid dashboard bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
