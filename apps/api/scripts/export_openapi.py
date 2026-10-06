"""Write the API's OpenAPI schema to a file. Used to generate the web app's TypeScript types."""

import json
import os
import sys
from pathlib import Path

# The schema does not depend on real config; placeholders let this run without a .env.
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from app.main import create_app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
