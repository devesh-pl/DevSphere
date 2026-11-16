"""Safely inspect and delete owned DevSphere deployments."""

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request


AUTH_URL = "http://127.0.0.1:8001"
DEPLOY_URL = "http://127.0.0.1:8005"


def api(method, url, token=None, payload=None):
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(payload).encode() if payload is not None else None

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
            return response.status, json.loads(data) if data else {}

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")

        try:
            detail = json.loads(body)
        except ValueError:
            detail = {"detail": body}

        return error.code, detail


def login():
    print("\nDevSphere developer authentication")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    status, result = api(
        "POST",
        AUTH_URL + "/auth/login",
        payload={"email": email, "password": password},
    )

    if status != 200 or not result.get("access_token"):
        raise RuntimeError(f"Login failed (HTTP {status})")

    token = result["access_token"]

    status, account = api("GET", AUTH_URL + "/auth/me", token)

    if status != 200:
        raise RuntimeError("Could not verify developer identity")

    print(f"Authenticated: {account.get('email', email)}")
    return token


def list_deployments(token):
    status, result = api(
        "GET",
        DEPLOY_URL + "/deployments",
        token,
    )

    if status != 200 or not isinstance(result, list):
        raise RuntimeError(
            f"Deployment listing failed: HTTP {status}, {result}"
        )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Inspect or delete your own DevSphere deployments."
    )

    parser.add_argument(
        "--delete",
        action="append",
        default=[],
        metavar="DEPLOYMENT_ID",
        help="Exact deployment UUID to delete; repeat for more IDs",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the explicitly selected deployments",
    )

    args = parser.parse_args()

    if args.apply and not args.delete:
        parser.error("--apply requires at least one --delete ID")

    token = login()
    records = list_deployments(token)

    active = {
        item["id"]: item
        for item in records
        if item.get("status") != "deleted"
    }

    print("\n===== YOUR ACTIVE DEPLOYMENTS =====\n")

    if not active:
        print("No active deployments found.")

    for item in active.values():
        print(
            f"{item['id']}  "
            f"{item['name']}  "
            f"{item['status']}  "
            f"replicas={item['replicas']}"
        )

    if not args.delete:
        print("\nREAD-ONLY AUDIT COMPLETE")
        print("No Kubernetes resources were changed.")
        return

    ids = list(dict.fromkeys(args.delete))
    selected = []

    for deployment_id in ids:
        item = active.get(deployment_id)

        if item is None:
            raise RuntimeError(
                f"Deployment {deployment_id} is not an active "
                "deployment owned by this account."
            )

        selected.append(item)

    print("\n===== SELECTED FOR DELETION =====\n")

    for item in selected:
        print(f"{item['name']}  ({item['id']})")

    if not args.apply:
        print("\nDRY RUN: Nothing has been deleted.")
        print("Add --apply to perform these deletions.")
        return

    print(
        "\nWARNING: These Kubernetes Deployments and Services "
        "will be deleted."
    )

    confirmation = input(
        f"Type DELETE {len(selected)} to confirm: "
    ).strip()

    if confirmation != f"DELETE {len(selected)}":
        print("Cancelled. No deletions submitted.")
        return

    failed = 0

    for item in selected:
        status, result = api(
            "DELETE",
            DEPLOY_URL + f"/deployments/{item['id']}",
            token,
        )

        if status == 200 and result.get("status") == "deleted":
            print(f"PASS: Deleted {item['name']}")
        else:
            failed += 1
            print(
                f"FAIL: {item['name']} "
                f"(HTTP {status}: {result})"
            )

    print("\nCleanup complete.")

    if failed:
        print(f"{failed} deletion(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, urllib.error.URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
