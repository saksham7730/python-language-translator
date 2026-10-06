"""Tests for US-09: command-line translator. main() is called directly with an argument list."""
import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from deep_translator.exceptions import TooManyRequests
from django.test import TestCase

import cli
from translator.models import Translation

from .helpers import EngineMocksMixin


class CliTests(EngineMocksMixin, TestCase):
    def run_cli(self, *argv):
        """Run cli.main() and capture what it prints. Returns (exit_code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch("cli.setup_django"):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_translate_text_prints_and_saves(self):
        code, out, _ = self.run_cli("Good", "morning,", "how", "are", "you", "today?", "-t", "hi")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(out.strip(), "नमस्ते")
        t = Translation.objects.get()
        self.assertEqual(t.origin, Translation.Origin.CLI)
        self.assertEqual(t.source_text, "Good morning, how are you today?")

    def test_language_names_work(self):
        self.run_cli("Bonjour mes amis", "-s", "French", "-t", "hindi")
        self.google.assert_called_once_with(source="fr", target="hi")

    def test_no_save(self):
        self.run_cli("Hello there", "-t", "hi", "--no-save")
        self.assertEqual(Translation.objects.count(), 0)

    def test_verbose_shows_engine_on_stderr(self):
        _, out, err = self.run_cli("Good morning, how are you today?", "-t", "hi", "-v")
        self.assertNotIn("via", out)          # stdout stays clean
        self.assertIn("English -> Hindi", err)
        self.assertIn("via Google", err)

    def test_unknown_language_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as ctx, redirect_stderr(io.StringIO()):
            self.run_cli("Hello", "-t", "klingon")
        self.assertEqual(ctx.exception.code, cli.EXIT_USAGE)

    def test_translation_failure_exit_code(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        self.mymemory.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", "ERROR"):
            code, _, err = self.run_cli("Good morning, how are you today?", "-t", "hi")
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("too many requests", err)

    def test_file_in_and_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "in.txt"), Path(tmp, "out.txt")
            src.write_text("Good morning, how are you today?", encoding="utf-8")
            code, _, _ = self.run_cli("--file", str(src), "-t", "hi", "-o", str(dst))
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(dst.read_text(encoding="utf-8").strip(), "नमस्ते")

    def test_missing_file(self):
        code, _, err = self.run_cli("--file", "does-not-exist.txt", "-t", "hi")
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("File not found", err)

    def test_list_languages_with_search(self):
        code, out, _ = self.run_cli("--list-langs", "--search", "hin")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("hi", out)
        self.assertIn("Hindi", out)
        self.assertNotIn("French", out)

    def test_history(self):
        Translation.objects.create(source_text="Hello", translated_text="नमस्ते", source_lang="en", target_lang="hi")
        _, out, _ = self.run_cli("--history", "-n", "5")
        self.assertIn("en -> hi", out)
        self.assertIn("नमस्ते", out)

    def test_interactive_mode(self):
        with patch("builtins.input", side_effect=["Good morning, how are you today?", "quit"]):
            code, out, _ = self.run_cli("-t", "hi")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("नमस्ते", out)
        self.assertEqual(Translation.objects.count(), 1)

    def test_history_shows_multiline_text_on_one_line(self):
        Translation.objects.create(source_text="Line one\nLine two", translated_text="पहली\nदूसरी",
                                   source_lang="en", target_lang="hi")
        _, out, _ = self.run_cli("--history")
        self.assertIn("Line one Line two", out)
        self.assertIn("पहली दूसरी", out)

    def test_one_line_truncates_long_text(self):
        self.assertEqual(cli.one_line("a " * 100, width=10), "a a a a a…")
