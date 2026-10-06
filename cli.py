#!/usr/bin/env python
"""Command-line translator (US-09).

Examples:
    python cli.py "Good morning" -t hi            translate text (auto-detect the source)
    python cli.py "Bonjour" -s fr -t english      language codes OR names both work
    python cli.py --file notes.txt -t mr -o out.txt
    python cli.py --list-langs                    show every supported language
    python cli.py --list-langs --search ind       ...or only the matching ones
    python cli.py --history -n 5                  last 5 saved translations
    python cli.py                                 interactive mode (type, Enter, repeat)

The translation itself goes to stdout; extra information goes to stderr, so
`python cli.py "Hi" -t hi > out.txt` saves only the translation.
Translations are saved to the same history as the website (origin = "cli").
"""
import argparse
import os
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1    # the translation (or reading the file) failed
EXIT_USAGE = 2    # wrong arguments (argparse also uses 2)
MAX_FILE_CHARS = 5000


def setup_django():
    """Load Django so the CLI can use the same services, settings (.env) and database as the website."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "translator_project.settings")
    import django
    django.setup()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Translate text between 100+ languages from the terminal.",
        epilog='Example: python cli.py "Good morning" -t hi',
    )
    parser.add_argument("text", nargs="*", help="text to translate (leave empty for interactive mode)")
    parser.add_argument("-t", "--to", default="en", help="target language code or name (default: en)")
    parser.add_argument("-s", "--source", default="auto", help="source language (default: auto-detect)")
    parser.add_argument("-f", "--file", type=Path, help="translate the contents of a UTF-8 .txt file")
    parser.add_argument("-o", "--output", type=Path, help="also write the translation to this file")
    parser.add_argument("--no-save", action="store_true", help="don't save to the history")
    parser.add_argument("-v", "--verbose", action="store_true", help="show detected language and engine")
    parser.add_argument("--list-langs", action="store_true", help="list supported languages and exit")
    parser.add_argument("--search", help="with --list-langs: only languages whose name or code contains this")
    parser.add_argument("--history", action="store_true", help="show recent translations and exit")
    parser.add_argument("-n", type=int, default=10, help="with --history: how many to show (default: 10)")
    return parser


def info(message):
    """Messages for the human go to stderr, so stdout only contains the translation."""
    print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def list_languages(search=None):
    from translator.services.languages import language_choices

    needle = (search or "").lower()
    rows = [(code, name) for code, name in language_choices()
            if needle in code.lower() or needle in name.lower()]   # list comprehension as a filter
    for code, name in rows:
        print(f"{code:<10} {name}")
    info(f"\n{len(rows)} language(s)")
    return EXIT_OK


def show_history(limit):
    from translator.models import Translation

    rows = Translation.objects.all()[:max(limit, 1)]   # slicing a QuerySet becomes SQL "LIMIT"
    if not rows:
        info("No translations saved yet.")
        return EXIT_OK
    for t in rows:
        when = t.created_at.astimezone().strftime("%d %b %H:%M")
        print(f"[{when}] {t.source_lang} -> {t.target_lang} ({t.get_origin_display()})")
        print(f"   {t.source_text[:70]}")
        print(f"   {t.translated_text[:70]}")
    return EXIT_OK


def resolve_languages(parser, args):
    """Turn codes or names into codes; stop with a usage error if one is unknown."""
    from translator.services.languages import AUTO, find_language_code

    target = find_language_code(args.to)
    if not target:
        parser.error(f"unknown target language '{args.to}' (see --list-langs)")
    source = AUTO if args.source.lower() == AUTO else find_language_code(args.source)
    if not source:
        parser.error(f"unknown source language '{args.source}' (see --list-langs)")
    return source, target


def read_text_file(path):
    """Read a UTF-8 text file. Raises ValueError with a friendly message on problems."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not a UTF-8 text file.")
    if len(text) > MAX_FILE_CHARS:
        raise ValueError(f"{path} has {len(text)} characters; the limit is {MAX_FILE_CHARS}.")
    return text


def translate_once(text, source, target, args):
    """Translate one piece of text, print it, optionally save it. Returns an exit code."""
    from translator.exceptions import TranslationError
    from translator.models import Translation
    from translator.services.engine import translate_text
    from translator.services.languages import get_language_name

    try:
        result = translate_text(text, target, source)
    except TranslationError as exc:
        info(f"Error: {exc}")
        return EXIT_ERROR

    print(result.translated_text)
    if args.verbose:
        detected = f" (detected: {result.detection.name})" if result.detection and result.detection.reliable else ""
        info(f"[{get_language_name(result.source_lang)} -> {get_language_name(target)}{detected} · via {result.engine_name}]")
    if args.output:
        args.output.write_text(result.translated_text + "\n", encoding="utf-8")
        info(f"Saved translation to {args.output}")
    if not args.no_save:
        Translation.from_result(result, origin=Translation.Origin.CLI)
    return EXIT_OK


def interactive(source, target, args):
    """Keep asking for text until the user types a blank line, 'quit', or presses Ctrl+C."""
    from translator.services.languages import get_language_name

    info(f"Interactive mode: {get_language_name(source)} -> {get_language_name(target)}. "
         "Type text and press Enter. Blank line or 'quit' to exit.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):   # Ctrl+Z/Ctrl+D or Ctrl+C
            info("")
            break
        if not text or text.lower() in {"quit", "exit", "q"}:
            break
        translate_once(text, source, target, args)
    return EXIT_OK


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # Windows terminals default to a legacy code page; force UTF-8 so Hindi etc. print
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    setup_django()

    if args.list_langs:
        return list_languages(args.search)
    if args.history:
        return show_history(args.n)

    source, target = resolve_languages(parser, args)

    if args.file and args.text:
        parser.error("give either text or --file, not both")
    if args.file:
        try:
            text = read_text_file(args.file)
        except ValueError as exc:
            info(f"Error: {exc}")
            return EXIT_ERROR
        return translate_once(text, source, target, args)
    if args.text:
        return translate_once(" ".join(args.text), source, target, args)
    return interactive(source, target, args)


if __name__ == "__main__":
    sys.exit(main())
