"""Check configured HTTPS trust and /models without sending credentials or project data."""

import argparse
import json
import os
from pathlib import Path
import sys
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai_tls import open_ai_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.environ.get("PARKHAVEN_AI_ENDPOINT"))
    args = parser.parse_args()
    if not args.endpoint:
        parser.error("gebruik --endpoint of stel PARKHAVEN_AI_ENDPOINT in")
    url = args.endpoint.rstrip("/") + "/models"
    try:
        with open_ai_request(request.Request(url, headers={"Accept": "application/json"}), timeout=20) as response:
            print(f"TLS verified; GET {url}: HTTP {response.status}")
            body = response.read()
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                content_type = response.headers.get_content_type()
                print(
                    f"Endpoint returned {content_type}, not a JSON model response. "
                    "Use the direct OpenAI-compatible API endpoint.", file=sys.stderr,
                )
                return 1
            print("Model IDs:", [model.get("id") for model in payload.get("data", [])])
    except error.HTTPError as exc:
        print(f"TLS verified; GET {url}: HTTP {exc.code}")
        if exc.code in (401, 403):
            print("Authentication is required. No API key was sent by this check.")
            print("Authentication challenge:", exc.headers.get("WWW-Authenticate", "not specified"))
        else:
            raise


if __name__ == "__main__":
    raise SystemExit(main())
