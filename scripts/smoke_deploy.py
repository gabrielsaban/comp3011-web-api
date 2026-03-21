from __future__ import annotations

import argparse
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class Check:
    name: str
    method: str
    path: str
    expected_status: int
    json: dict[str, object] | None = None


def _run_check(client: httpx.Client, check: Check) -> tuple[bool, str]:
    if check.method == "GET":
        response = client.get(check.path)
    elif check.method == "POST":
        response = client.post(check.path, json=check.json)
    else:
        return False, f"unsupported method {check.method}"

    if response.status_code != check.expected_status:
        preview = response.text[:180]
        return (
            False,
            f"status={response.status_code}, expected={check.expected_status}, body={preview}",
        )
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment smoke-check runner.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--check-analytics",
        action="store_true",
        help="Run additional analytics checks that expect imported data to exist.",
    )
    args = parser.parse_args()

    checks = [
        Check("health", "GET", "/health", 200),
        Check("regions", "GET", "/api/v1/regions", 200),
        Check("reference", "GET", "/api/v1/reference/conditions", 200),
        Check("route-risk-scoring-model", "GET", "/api/v1/analytics/route-risk/scoring-model", 200),
    ]
    if args.check_analytics:
        checks.append(Check("annual-trend", "GET", "/api/v1/analytics/annual-trend", 200))
        checks.append(
            Check(
                "route-risk",
                "POST",
                "/api/v1/analytics/route-risk",
                200,
                json={
                    "waypoints": [[51.5074, -0.1278], [51.5079, -0.125], [51.5082, -0.122]],
                },
            )
        )

    failures: list[str] = []
    with httpx.Client(base_url=args.base_url, timeout=args.timeout_seconds) as client:
        for check in checks:
            ok, detail = _run_check(client, check)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {check.name}: {detail}")
            if not ok:
                failures.append(check.name)

    if failures:
        print(f"\nSmoke checks failed: {', '.join(failures)}")
        raise SystemExit(1)

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
