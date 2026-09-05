"""Application configuration.

Values are read from environment variables with sensible defaults for local
development. Production overrides should go through the environment, not by
editing this file.
"""

import os
from pathlib import Path


CONTENT_VERSION = os.getenv("TINY_IPA_CONTENT_VERSION", "development")
RELEASE_ID = os.getenv("TINY_IPA_RELEASE_ID", "development")
RELEASE_COMMIT = os.getenv("TINY_IPA_RELEASE_COMMIT", "development")
RELEASE_TAG = os.getenv("TINY_IPA_RELEASE_TAG", "")
DB_PATH = os.getenv(
    "TINY_IPA_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "tiny_ipa.sqlite"),
)
DB_READY = os.path.isfile(DB_PATH)
