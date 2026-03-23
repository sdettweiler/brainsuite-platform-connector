#!/usr/bin/env python3
"""Interactive setup script for BrainSuite Platform Connector.

Prompts for required secrets and generates a valid .env file.
Auto-generates SECRET_KEY and TOKEN_ENCRYPTION_KEY.

Usage:
    python3 scripts/setup.py           # Interactive mode
    python3 scripts/setup.py --dry-run # Print env content without writing
"""
import getpass
import secrets
import subprocess
import sys
import time
from pathlib import Path

# cryptography is already in requirements.txt (42.0.4)
from cryptography.fernet import Fernet


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    """Prompt user for input with optional default and hidden input for secrets.

    Returns the default value immediately if stdin is not a TTY (e.g. piped /dev/null).
    """
    if not sys.stdin.isatty():
        return default
    if default:
        display = f"{label} [{default}]: "
    else:
        display = f"{label}: "
    try:
        if secret:
            value = getpass.getpass(display)
        else:
            value = input(display)
    except EOFError:
        return default
    return value.strip() or default


def main():
    dry_run = "--dry-run" in sys.argv

    if not dry_run and ENV_PATH.exists() and sys.stdin.isatty():
        confirm = input(f"\n.env already exists at {ENV_PATH}. Overwrite? [y/N]: ")
        if confirm.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    print("\n=== BrainSuite Platform Connector Setup ===\n")
    print("Press Enter to accept [default] values.\n")

    # --- Database ---
    print("--- Database ---")
    pg_user = prompt("PostgreSQL user", "brainsuite")
    pg_password = prompt("PostgreSQL password", "brainsuite_dev", secret=True)
    pg_db = prompt("PostgreSQL database name", "platform_connectors")

    # --- Application URL ---
    print("\n--- Application ---")
    base_url = prompt("Base URL (public URL in production)", "http://localhost:8000")
    scheduler_delay = prompt("Scheduler startup delay seconds (15 for production)", "0")

    # --- Redis ---
    print("\n--- Redis ---")
    redis_url = prompt("Redis URL", "redis://redis:6379/0")

    # --- Object Storage (S3/MinIO) ---
    print("\n--- Object Storage (S3/MinIO) ---")
    print("  For local dev: use MinIO defaults below")
    print("  For production: enter real AWS S3 credentials\n")
    s3_endpoint = prompt("S3 endpoint URL (blank for real AWS S3)", "http://minio:9000")
    s3_bucket = prompt("S3 bucket name", "brainsuite-assets")
    aws_key = prompt("AWS access key ID", "minioadmin")
    aws_secret = prompt("AWS secret access key", "minioadmin123", secret=True)
    aws_region = prompt("AWS region", "us-east-1")

    # --- Auto-generated security keys ---
    print("\n--- Security Keys (auto-generated) ---")
    secret_key = secrets.token_hex(32)
    fernet_key = Fernet.generate_key().decode()
    print(f"  Generated SECRET_KEY:          {secret_key}")
    print(f"  Generated TOKEN_ENCRYPTION_KEY: {fernet_key}")
    if not dry_run and sys.stdin.isatty():
        confirm = input("\nAccept these generated keys? [Y/n]: ")
        if confirm.lower() == "n":
            secret_key = prompt("Enter custom SECRET_KEY (64 hex chars)")
            fernet_key = prompt("Enter custom TOKEN_ENCRYPTION_KEY (Fernet key)")

    # --- Meta / Facebook ---
    print("\n--- Meta / Facebook OAuth ---")
    print("  Create at: https://developers.facebook.com/apps/")
    meta_app_id = prompt("Meta App ID (blank to skip)")
    meta_app_secret = prompt("Meta App Secret", secret=True) if meta_app_id else ""

    # --- TikTok ---
    print("\n--- TikTok OAuth ---")
    print("  Create at: https://ads.tiktok.com/marketing_api/apps/")
    tiktok_app_id = prompt("TikTok App ID (blank to skip)")
    tiktok_app_secret = prompt("TikTok App Secret", secret=True) if tiktok_app_id else ""

    # --- Google ---
    print("\n--- Google / YouTube OAuth ---")
    print("  Create at: https://console.developers.google.com/")
    google_client_id = prompt("Google Client ID (blank to skip)")
    google_client_secret = prompt("Google Client Secret", secret=True) if google_client_id else ""
    google_dev_token = prompt("Google Ads Developer Token (blank to skip)") if google_client_id else ""

    # --- DV360 ---
    print("\n--- DV360 OAuth (optional) ---")
    dv360_client_id = prompt("DV360 Client ID (blank to skip)")
    dv360_client_secret = prompt("DV360 Client Secret", secret=True) if dv360_client_id else ""

    # --- BrainSuite ---
    print("\n--- BrainSuite API ---")
    print("  OAuth 2.0 Client Credentials (from BrainSuite dashboard)")
    brainsuite_client_id = prompt("BrainSuite Client ID (blank to skip)")
    brainsuite_client_secret = prompt("BrainSuite Client Secret", secret=True) if brainsuite_client_id else ""
    brainsuite_base_url = prompt("BrainSuite API base URL", "https://api.brainsuite.ai") if brainsuite_client_id else "https://api.brainsuite.ai"
    brainsuite_auth_url = prompt("BrainSuite Auth URL", "https://auth.brainsuite.ai/oauth2/token") if brainsuite_client_id else "https://auth.brainsuite.ai/oauth2/token"

    # --- Currency ---
    print("\n--- Currency Conversion ---")
    print("  Get free key at: https://www.exchangerate-api.com/")
    exchange_key = prompt("Exchange Rate API key (blank to skip)")

    # --- Build .env content ---
    lines = [
        "# === BrainSuite Platform Connector ===",
        "# Generated by scripts/setup.py",
        "",
        "# --- Database ---",
        f"POSTGRES_USER={pg_user}",
        f"POSTGRES_PASSWORD={pg_password}",
        f"POSTGRES_DB={pg_db}",
        "",
        "# --- Security ---",
        f"SECRET_KEY={secret_key}",
        f"TOKEN_ENCRYPTION_KEY={fernet_key}",
        "",
        "# --- Application ---",
        f"BASE_URL={base_url}",
        f"SCHEDULER_STARTUP_DELAY_SECONDS={scheduler_delay}",
        "",
        "# --- Redis ---",
        f"REDIS_URL={redis_url}",
        "",
        "# --- Object Storage (S3/MinIO) ---",
        f"S3_ENDPOINT_URL={s3_endpoint}",
        f"S3_BUCKET_NAME={s3_bucket}",
        f"AWS_ACCESS_KEY_ID={aws_key}",
        f"AWS_SECRET_ACCESS_KEY={aws_secret}",
        f"AWS_REGION={aws_region}",
        "",
        "# --- Meta / Facebook ---",
        f"META_APP_ID={meta_app_id}",
        f"META_APP_SECRET={meta_app_secret}",
        f"META_REDIRECT_URI={base_url}/api/v1/platforms/oauth/callback/meta",
        "",
        "# --- TikTok ---",
        f"TIKTOK_APP_ID={tiktok_app_id}",
        f"TIKTOK_APP_SECRET={tiktok_app_secret}",
        f"TIKTOK_REDIRECT_URI={base_url}/api/v1/platforms/oauth/callback/tiktok",
        "",
        "# --- Google / YouTube ---",
        f"GOOGLE_CLIENT_ID={google_client_id}",
        f"GOOGLE_CLIENT_SECRET={google_client_secret}",
        f"GOOGLE_REDIRECT_URI={base_url}/api/v1/platforms/oauth/callback/google",
        f"GOOGLE_DEVELOPER_TOKEN={google_dev_token}",
        "",
        "# --- DV360 ---",
        f"DV360_CLIENT_ID={dv360_client_id}",
        f"DV360_CLIENT_SECRET={dv360_client_secret}",
        "",
        "# --- BrainSuite ---",
        f"BRAINSUITE_CLIENT_ID={brainsuite_client_id}",
        f"BRAINSUITE_CLIENT_SECRET={brainsuite_client_secret}",
        f"BRAINSUITE_BASE_URL={brainsuite_base_url}",
        f"BRAINSUITE_AUTH_URL={brainsuite_auth_url}",
        "",
        "# --- Currency ---",
        f"EXCHANGE_RATE_API_KEY={exchange_key}",
        "",
    ]

    content = "\n".join(lines)

    if dry_run:
        print("\n--- DRY RUN: Generated .env content ---\n")
        print(content)
        print("--- END DRY RUN ---")
        sys.exit(0)

    ENV_PATH.write_text(content)
    print(f"\n.env written to {ENV_PATH}")

    # --- Create MinIO bucket if Docker stack is running ---
    _create_minio_bucket(s3_bucket, aws_key, aws_secret)

    print("\nNext steps:")
    print("  1. Run: make dev")
    print("  2. Open: http://localhost:4200 (frontend)")
    print("  3. Open: http://localhost:9001 (MinIO console)")


def _create_minio_bucket(bucket: str, access_key: str, secret_key: str) -> None:
    """Create the MinIO bucket if the stack is already running."""
    # Check if minio container is up
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "brainsuite_minio"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        print("\nMinIO container not running — bucket will be created on first 'make dev'.")
        print(f"  To create manually: docker exec brainsuite_minio mc alias set local http://localhost:9000 {access_key} {secret_key} && docker exec brainsuite_minio mc mb local/{bucket}")
        return

    print(f"\nCreating MinIO bucket '{bucket}'...")
    mc = "docker exec brainsuite_minio mc"
    cmds = [
        f"{mc} alias set local http://localhost:9000 {access_key} {secret_key}",
        f"{mc} mb --ignore-existing local/{bucket}",
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  Warning: {r.stderr.strip() or r.stdout.strip()}")
            return
    print(f"  Bucket '{bucket}' ready.")


if __name__ == "__main__":
    main()
