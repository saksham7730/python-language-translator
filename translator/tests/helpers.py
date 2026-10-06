"""Shared test helpers.

EngineMocksMixin replaces BOTH translation engines with mocks for every test,
so no test ever calls the real internet, and resets the engine cool-downs.
"""
import os
from unittest.mock import patch

from translator.services import engine


class EngineMocksMixin:
    def setUp(self):
        super().setUp()
        engine.reset_cooldowns()
        # Tests must not depend on the developer's .env (e.g. PRIMARY_ENGINE=mymemory)
        env_patch = patch.dict(os.environ, {"PRIMARY_ENGINE": "google", "GEMINI_API_KEY": ""})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        google_patch = patch("translator.services.engine.GoogleTranslator")
        mymemory_patch = patch("translator.services.engine.MyMemoryTranslator")
        self.google = google_patch.start()
        self.mymemory = mymemory_patch.start()
        self.addCleanup(google_patch.stop)
        self.addCleanup(mymemory_patch.stop)
        self.addCleanup(engine.reset_cooldowns)
        # Sensible defaults; individual tests override them
        self.google.return_value.translate.return_value = "नमस्ते"
        self.mymemory.return_value.translate.return_value = "नमस्ते (backup)"
