"""OCR backend integration utilities."""

from __future__ import annotations

import base64
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[assignment]


def extract_text(image_bytes: bytes, backend: str | None = None) -> str:
    """Extract text from image bytes using the configured OCR backend.

    Args:
        image_bytes: Raw image data.
        backend: Optional backend name overriding ``OCR_BACKEND`` env var.

    Returns:
        Recognised text. Returns an empty string if the backend is ``"none"``.

    Raises:
        ValueError: If an unsupported backend is specified.
        ImportError: If the OpenAI backend is selected but the package is missing.
    """
    backend_name = (backend or os.getenv("OCR_BACKEND", "openai")).lower()

    if backend_name == "none":
        return ""

    if backend_name == "openai":
        if OpenAI is None:  # pragma: no cover - defensive
            msg = "openai package is required for the OpenAI OCR backend"
            raise ImportError(msg)
        client = OpenAI()
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image": {"b64_json": b64}},
                        {
                            "type": "text",
                            "text": "Transcribe the text in this image.",
                        },
                    ],
                }
            ],
        )
        return getattr(resp, "output_text", "").strip()

    msg = f"Unsupported OCR backend: {backend_name}"
    raise ValueError(msg)
