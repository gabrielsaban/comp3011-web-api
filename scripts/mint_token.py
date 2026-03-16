from __future__ import annotations

import argparse

from app.core.auth import create_access_token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mint a signed JWT for local API testing.")
    parser.add_argument("--sub", default="local-dev-user", help="Token subject claim.")
    parser.add_argument(
        "--role",
        required=True,
        choices=("editor", "admin"),
        help="Role claim for authorization checks.",
    )
    parser.add_argument(
        "--expires-minutes",
        type=int,
        default=None,
        help="Optional token TTL override in minutes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = create_access_token(
        subject=args.sub,
        role=args.role,
        expires_minutes=args.expires_minutes,
    )
    print(token)


if __name__ == "__main__":
    main()
