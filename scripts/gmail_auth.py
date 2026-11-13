import os
from pathlib import Path

from dotenv import load_dotenv

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def main() -> None:
    load_dotenv()
    client_secrets = os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRETS",
        ".secrets/google-oauth-client.json",
    )
    token_path = Path(
        os.getenv("GMAIL_TOKEN_FILE", ".secrets/gmail-token.json")
    )
    if not Path(client_secrets).is_file():
        raise FileNotFoundError(
            "Google OAuth client JSON is missing. Set "
            "GOOGLE_OAUTH_CLIENT_SECRETS to your local Desktop OAuth client file."
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Install the project requirements before starting Gmail OAuth."
        ) from exc

    flow = InstalledAppFlow.from_client_secrets_file(
        client_secrets,
        scopes=[GMAIL_SEND_SCOPE],
    )
    credentials = flow.run_local_server(port=0, access_type="offline")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    print(f"Gmail OAuth token saved to {token_path}.")


if __name__ == "__main__":
    main()
