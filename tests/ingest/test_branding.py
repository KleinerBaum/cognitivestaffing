"""Tests for branding asset extraction."""

from __future__ import annotations

from io import BytesIO

import pytest

PIL_Image = pytest.importorskip("PIL.Image")

from ingest.branding import BrandAssets, extract_brand_assets


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    PIL_Image.new("RGB", (4, 4), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_brand_assets_prefers_theme_color(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="theme-color" content="#12ab34" />
      </head>
      <body>
        <header>
          <img src="/static/logo.svg" alt="ACME Company Logo" width="180" height="60" />
        </header>
        <p class="claim">Innovate. Inspire. Impact.</p>
      </body>
    </html>
    """

    monkeypatch.setattr("ingest.branding._download_image", lambda _: _png_bytes((10, 200, 30)))

    assets = extract_brand_assets(html, base_url="https://example.com/jobs")

    assert isinstance(assets, BrandAssets)
    assert assets.logo_url == "https://example.com/static/logo.svg"
    assert assets.icon_url == "https://example.com/favicon.ico"
    assert assets.brand_color == "#12AB34"
    assert assets.claim == "Innovate. Inspire. Impact."


def test_extract_brand_assets_uses_logo_color(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
      <body>
        <img src="logo.png" alt="Main Logo" width="200" height="120" />
      </body>
    </html>
    """

    monkeypatch.setattr("ingest.branding._download_image", lambda _: _png_bytes((10, 20, 30)))

    assets = extract_brand_assets(html, base_url="https://brand.example")

    assert assets.logo_url == "https://brand.example/logo.png"
    assert assets.brand_color == "#0A141E"
    assert assets.icon_url is None
    assert assets.claim is None


def test_extract_brand_assets_handles_empty_html() -> None:
    assets = extract_brand_assets("", base_url=None)

    assert assets == BrandAssets()


def test_extract_brand_assets_uses_meta_image(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
      <head>
        <meta property="og:image" content="/assets/og-logo.png" />
      </head>
      <body>
        <img src="/images/team.jpg" alt="Team photo" width="400" height="250" />
      </body>
    </html>
    """

    monkeypatch.setattr(
        "ingest.branding._download_image",
        lambda _: _png_bytes((200, 50, 50)),
    )

    assets = extract_brand_assets(html, base_url="https://logo.example/careers")

    assert assets.logo_url == "https://logo.example/assets/og-logo.png"
    assert assets.brand_color == "#C83232"
