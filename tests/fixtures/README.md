# Test Fixtures

## `job_ad_simple_en_pdf_base64.txt`

This file stores the PDF fixture used by `tests/test_extraction_prompts.py` as a base64-encoded string. The original binary PDF is intentionally kept out of version control to avoid large binary diffs.

To regenerate the encoded payload:

1. Create or update `tests/fixtures/job_ad_simple_en.pdf` with the desired contents.
2. Run the snippet below to refresh the base64 representation:

```bash
python - <<'PY'
from pathlib import Path
import base64
pdf_path = Path("tests/fixtures/job_ad_simple_en.pdf")
encoded_path = Path("tests/fixtures/job_ad_simple_en_pdf_base64.txt")
encoded = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
encoded_path.write_text(encoded + "\n", encoding="utf-8")
print(f"Wrote {encoded_path}")
PY
```

Remember to delete the binary PDF afterwards (or keep it locally) so it doesn't get added to the repository.
