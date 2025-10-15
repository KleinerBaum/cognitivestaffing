"""Utility to re-embed an OpenAI vector store with the configured embedding model.

The script clones all files from a source store into a freshly created target
store that uses :data:`config.EMBED_MODEL` (``text-embedding-3-large``). Run it
after upgrading the embedding model so that every document is reprocessed with
the 3,072-dimensional encoder.
"""

from __future__ import annotations

import argparse
import io

from openai import OpenAI

from config import EMBED_MODEL


def _collect_file_ids(client: OpenAI, vector_store_id: str) -> list[str]:
    file_ids: list[str] = []
    cursor: str | None = None
    while True:
        response = client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=100,
            after=cursor,
        )
        file_ids.extend(entry.id for entry in response.data)
        if not getattr(response, "has_more", False):
            break
        cursor = getattr(response, "last_id", None)
        if not cursor and response.data:
            cursor = response.data[-1].id
        if not cursor:
            break
    return file_ids


def _download_file(client: OpenAI, file_id: str) -> tuple[str, bytes]:
    metadata = client.files.retrieve(file_id)
    filename = getattr(metadata, "filename", None) or file_id
    content = client.files.content(file_id)
    payload = content.read()
    if not isinstance(payload, (bytes, bytearray)):
        raise RuntimeError(f"Unexpected payload type for file {file_id}: {type(payload)!r}")
    return filename, bytes(payload)


def _upload_file(client: OpenAI, vector_store_id: str, filename: str, payload: bytes) -> str:
    buffer = io.BytesIO(payload)
    buffer.seek(0)
    new_file = client.files.create(file=(filename, buffer), purpose="assistants")
    client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=new_file.id)
    return new_file.id


def _rebuild_store(source_store_id: str, *, embedding_model: str, name: str | None) -> str:
    client = OpenAI()
    target = client.vector_stores.create(
        name=name or f"{source_store_id}-te3large",
        embedding_model=embedding_model,
    )
    file_ids = _collect_file_ids(client, source_store_id)
    if not file_ids:
        return target.id
    total = len(file_ids)
    for index, file_id in enumerate(file_ids, start=1):
        filename, payload = _download_file(client, file_id)
        new_file_id = _upload_file(client, target.id, filename, payload)
        print(f"[{index}/{total}] Re-embedded {filename} -> {new_file_id}")
    return target.id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="Vector store ID that currently points to text-embedding-3-small embeddings.",
    )
    parser.add_argument(
        "--name",
        help="Optional display name for the new vector store.",
    )
    parser.add_argument(
        "--embedding-model",
        default=EMBED_MODEL,
        help="Embedding model to apply during the rebuild (defaults to config.EMBED_MODEL).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_store_id = _rebuild_store(
        args.source,
        embedding_model=args.embedding_model,
        name=args.name,
    )
    print("Successfully rebuilt vector store.")
    print(f"Source: {args.source}")
    print(f"Target: {target_store_id}")
    print("Update VECTOR_STORE_ID to the new target once verification completes.")


if __name__ == "__main__":
    main()
