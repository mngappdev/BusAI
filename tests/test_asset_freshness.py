"""A kiosk browser must never keep running yesterday's JavaScript.

The trip panel once reported a 2-minute walk as 101 minutes. The fix shipped,
the server served it, and the kiosk kept showing 101 — it was still executing a
cached copy of trip-duration.js. Nothing told the browser to revalidate: the
script tags carried no version and the responses carried no Cache-Control, so
browsers fell back to heuristic caching and skipped the round trip entirely.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

STATIC_ASSETS = [
    "/static/js/i18n.js",
    "/static/js/trip-duration.js",
    "/static/js/view-router.js",
    "/static/img/bus2.jpg",
]


def _must_revalidate(cache_control):
    """True when the header forbids reusing a cached copy without asking us."""
    if not cache_control:
        return False
    value = cache_control.lower()
    return 'no-cache' in value or 'no-store' in value or 'max-age=0' in value


@pytest.mark.parametrize("path", STATIC_ASSETS)
def test_static_assets_must_be_revalidated(path):
    response = client.get(path)

    assert response.status_code == 200
    assert _must_revalidate(response.headers.get("cache-control")), (
        f"{path} may be served from cache without revalidating; "
        f"got Cache-Control={response.headers.get('cache-control')!r}"
    )


def test_index_must_be_revalidated():
    response = client.get("/")

    assert response.status_code == 200
    assert _must_revalidate(response.headers.get("cache-control"))


@pytest.mark.parametrize("path", STATIC_ASSETS)
def test_static_assets_still_carry_a_validator(path):
    """no-cache means "ask first", not "resend every time" — keep ETag so the
    revalidation is a cheap 304 rather than a full download."""
    response = client.get(path)

    assert response.headers.get("etag") or response.headers.get("last-modified")


@pytest.mark.parametrize("path", STATIC_ASSETS)
def test_unchanged_asset_revalidates_to_304(path):
    etag = client.get(path).headers.get("etag")
    assert etag, f"{path} has no ETag to revalidate against"

    response = client.get(path, headers={"If-None-Match": etag})

    assert response.status_code == 304, "revalidation should be cheap, not a full resend"


def test_static_assets_are_still_served_correctly():
    """The cache headers must not break what the kiosk actually loads."""
    js = client.get("/static/js/trip-duration.js")
    assert js.status_code == 200
    assert "computeDirectTripMinutes" in js.text

    img = client.get("/static/img/bus2.jpg")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/jpeg"
