"""Tests for US-10 (file upload + chunking) and US-11 (listen/copy buttons)."""
from deep_translator.exceptions import TooManyRequests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.exceptions import TranslationError
from translator.models import Translation
from translator.services.chunking import chunk_text
from translator.services.engine import MAX_DOCUMENT_CHARS, translate_long_text

from .helpers import EngineMocksMixin

LONG_TEXT = "\n".join(f"This is sentence number {i} of a long English document." for i in range(200))


class ChunkingTests(SimpleTestCase):
    def test_short_text_is_one_chunk(self):
        self.assertEqual(list(chunk_text("Hello", 100)), ["Hello"])

    def test_chunks_fit_and_rejoin_exactly(self):
        for size in (40, 500, 4500):
            chunks = list(chunk_text(LONG_TEXT, size))
            self.assertTrue(all(len(c) <= size for c in chunks))
            self.assertEqual("".join(chunks), LONG_TEXT)     # nothing lost, nothing added

    def test_long_sentence_and_long_word(self):
        text = "word " * 100 + "x" * 50
        chunks = list(chunk_text(text, 30))
        self.assertTrue(all(len(c) <= 30 for c in chunks))
        self.assertEqual("".join(chunks), text)

    def test_is_a_generator(self):
        self.assertTrue(hasattr(chunk_text("abc", 2), "__next__"))

    def test_hindi_danda_is_a_sentence_end(self):
        chunks = list(chunk_text("यह पहला वाक्य है। यह दूसरा वाक्य है।", 20))
        self.assertTrue(chunks[0].endswith("। "))


class LongTextEngineTests(EngineMocksMixin, SimpleTestCase):
    def test_long_text_is_translated_in_chunks(self):
        self.google.return_value.translate.side_effect = lambda text: text.upper()
        result = translate_long_text(LONG_TEXT, "hi")
        self.assertGreater(self.google.return_value.translate.call_count, 1)
        self.assertEqual(result.translated_text, LONG_TEXT.upper())     # line breaks kept
        self.assertEqual(result.source_lang, "en")                      # detected once for all chunks

    def test_short_text_uses_single_request(self):
        translate_long_text("Good morning, how are you today?", "hi")
        self.assertEqual(self.google.return_value.translate.call_count, 1)

    def test_too_long_text_is_rejected(self):
        with self.assertRaises(TranslationError):
            translate_long_text("a" * (MAX_DOCUMENT_CHARS + 1), "hi")

    def test_backup_engine_gets_small_pieces(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        self.mymemory.return_value.translate.side_effect = lambda text: "ok"
        with self.assertLogs("translator", "WARNING"):
            result = translate_long_text(LONG_TEXT, "hi")
        self.assertEqual(result.engine, "mymemory")
        self.assertTrue(result.used_fallback)
        sizes = [len(c.args[0]) for c in self.mymemory.return_value.translate.call_args_list]
        self.assertTrue(all(size <= 499 for size in sizes))


class FileUploadTests(EngineMocksMixin, TestCase):
    url = reverse("translator:file")

    def upload(self, content, name="notes.txt", target="hi"):
        file = SimpleUploadedFile(name, content if isinstance(content, bytes) else content.encode("utf-8"))
        return self.client.post(self.url, {"file": file, "source_lang": "auto", "target_lang": target})

    def test_upload_translates_saves_and_redirects(self):
        response = self.upload("Good morning, how are you today?")
        t = Translation.objects.get()
        self.assertRedirects(response, reverse("translator:detail", args=[t.pk]))
        self.assertEqual(t.origin, Translation.Origin.FILE)
        self.assertEqual(t.translated_text, "नमस्ते")

    def test_notepad_bom_is_removed(self):
        self.upload("﻿Good morning, how are you today?".encode("utf-8"))
        self.assertEqual(Translation.objects.get().source_text, "Good morning, how are you today?")

    def test_wrong_extension(self):
        self.assertContains(self.upload("hello", name="notes.pdf"), "Only .txt files are supported.")

    def test_not_utf8(self):
        self.assertContains(self.upload("café".encode("latin-1")), "must be saved as UTF-8")

    def test_empty_file(self):
        self.assertContains(self.upload("   "), "The file is empty.")

    def test_too_many_characters(self):
        self.assertContains(self.upload("a" * (MAX_DOCUMENT_CHARS + 1)), "The limit is 20,000")
        self.assertEqual(Translation.objects.count(), 0)


class DetailAndDownloadTests(TestCase):
    def setUp(self):
        self.t = Translation.objects.create(source_text="Hello\nWorld", translated_text="नमस्ते\nदुनिया",
                                            source_lang="en", target_lang="hi", char_count=11)

    def test_detail_page_has_listen_copy_and_download(self):
        response = self.client.get(reverse("translator:detail", args=[self.t.pk]))
        self.assertContains(response, 'data-speak="#detail-output"')
        self.assertContains(response, 'data-lang="hi"')
        self.assertContains(response, 'data-copy="#detail-output"')
        self.assertContains(response, reverse("translator:download", args=[self.t.pk]))

    def test_download_is_a_utf8_text_attachment(self):
        response = self.client.get(reverse("translator:download", args=[self.t.pk]))
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn(f'attachment; filename="translation-{self.t.pk}-hi.txt"', response["Content-Disposition"])
        self.assertEqual(response.content.decode("utf-8"), "नमस्ते\nदुनिया\n")

    def test_missing_translation_404(self):
        self.assertEqual(self.client.get(reverse("translator:download", args=[999])).status_code, 404)


class ListenButtonOnHomeTests(EngineMocksMixin, TestCase):
    def test_result_has_listen_and_copy_buttons(self):
        response = self.client.post(reverse("translator:home"), {"text": "Good morning, how are you today?",
                                    "source_lang": "auto", "target_lang": "hi"}, follow=True)
        self.assertContains(response, 'data-speak="#output-text"')
        self.assertContains(response, 'data-copy="#output-text"')
