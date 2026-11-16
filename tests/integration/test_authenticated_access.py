"""Verify authenticated access to DevSphere services."""

import getpass
import json
import urllib.error
import urllib.request


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
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
            return response.status, json.loads(data) if data else None

    except urllib.error.HTTPError as error:
        data = error.read()
        try:
            parsed = json.loads(data)
        except ValueError:
            parsed = None
        return error.code, parsed


def main():
    email = input("DevSphere email: ").strip()
    password = getpass.getpass("Password: ")

    status, login = api(
        "POST",
        "http://127.0.0.1:8001/auth/login",
        payload={"email": email, "password": password},
    )

    assert status == 200 and isinstance(login, dict), (
        f"Login failed: HTTP {status}"
    )

    token = login.get("access_token")
    assert token, "Missing access token"

    print("PASS: Developer authentication")

    checks = [
        ("Developer identity", "http://127.0.0.1:8001/auth/me"),
        ("Build jobs", "http://127.0.0.1:8006/builds"),
        ("Deployments", "http://127.0.0.1:8005/deployments"),
    ]

    for name, url in checks:
        status, result = api("GET", url, token=token)
        assert status == 200, f"{name}: HTTP {status}"

        if name == "Developer identity":
            assert isinstance(result, dict) and result.get("id")
        else:
            assert isinstance(result, list)

        print(f"PASS: {name}")

    print("\nALL AUTHENTICATED ACCESS TESTS PASSED")


if __name__ == "__main__":
    main()
