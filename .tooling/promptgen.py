#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TAGS: Dict[str, str] = {
    "bugfix": r"(fix|bug|error|exception|failing test|hotfix)",
    "feature": r"(feat|add|introduce|implement|new)",
    "refactor": r"(refactor|cleanup|rename|restructure)",
}


def guess_type(diff_text: str, last_commit_msg: str) -> str:
    """Guess the prompt template based on diff content and last commit message."""

    haystack = (diff_text[:20000] + " " + last_commit_msg).lower()
    for template, pattern in TAGS.items():
        if re.search(pattern, haystack):
            return template
    return "feature"


def collect_context(diff_text: str) -> Dict[str, object]:
    """Collect changed files and a truncated diff excerpt."""

    files: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            files.append(line.replace("+++ b/", "").strip())
    return {
        "files": sorted(set(files))[:100],
        "diff_excerpt": diff_text[:200000],
    }


def load_template(kind: str) -> str:
    template_path = Path(".tooling/templates") / f"{kind}.md"
    return template_path.read_text(encoding="utf-8")


def build_payload(kind: str, commit_message: str, context: Dict[str, object], template: str) -> Dict[str, object]:
    timestamp = datetime.utcnow().isoformat() + "Z"
    files = "\n".join(f"- {file}" for file in context["files"])
    diff_excerpt = str(context["diff_excerpt"])

    return {
        "kind": kind,
        "timestamp": timestamp,
        "commit_message": commit_message,
        "context": context,
        "prompt": template.format(
            FILES=files,
            DIFF=diff_excerpt,
            COMMIT_MSG=commit_message,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--out", default=".tooling/out_prompts")
    args = parser.parse_args()

    diff_text = sys.stdin.read() if args.diff else ""
    last_commit_msg = os.popen("git log -1 --pretty=%B").read().strip()

    kind = guess_type(diff_text, last_commit_msg)
    context = collect_context(diff_text)
    template = load_template(kind)
    payload = build_payload(kind, last_commit_msg, context, template)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{kind}.json"
    filename.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[promptgen] written: {filename}")


if __name__ == "__main__":
    main()
