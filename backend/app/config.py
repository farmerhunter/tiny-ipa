"""Application configuration.

Values are read from environment variables with sensible defaults for local
development. Production overrides should go through the environment, not by
editing this file.
"""

import os


CONTENT_VERSION = os.getenv("TINY_IPA_CONTENT_VERSION", "development")
DB_PATH = os.getenv("TINY_IPA_DB_PATH", "")
DB_READY = os.path.isfile(DB_PATH) if DB_PATH else False
