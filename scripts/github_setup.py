"""
One-time GitHub setup for this repository, using the GitHub CLI (gh).

Run it from the repository root, after the repo has been pushed to GitHub:

    python scripts/github_setup.py                # 1) labels, milestones, issues
    python scripts/github_setup.py --project 1    # 2) put the issues on Project board #1
    python scripts/github_setup.py --dry-run      # only print the gh commands

Re-running it is safe: anything that already exists is skipped.
"""

import argparse
import json
import subprocess
import sys

# ---------------------------------------------------------------------------
# Data: labels, sprints (milestones) and user stories
# ---------------------------------------------------------------------------

# (name, hex colour without '#', description)
LABELS = [
    ("feature", "1D76DB", "New functionality"),
    ("bug", "D73A4A", "Something isn't working"),
    ("docs", "0075CA", "Documentation"),
    ("ui", "C5DEF5", "Templates, CSS, front-end"),
    ("backend", "5319E7", "Views, models, services"),
    ("user-story", "FBCA04", "Agile user story"),
    ("chore", "BFD4F2", "Setup / maintenance, no user-facing change"),
    ("must-have", "B60205", "MoSCoW: Must have"),
    ("should-have", "FF9F1C", "MoSCoW: Should have"),
    ("could-have", "0E8A16", "MoSCoW: Could have"),
]

SPRINTS = {
    1: {"title": "Sprint 1 - Core Translation", "due": "2026-10-20",
        "description": "7 Oct - 20 Oct: translate, auto-detect, save history, error handling"},
    2: {"title": "Sprint 2 - History & CLI", "due": "2026-11-03",
        "description": "21 Oct - 3 Nov: history page, search/filter, delete, command-line tool"},
    3: {"title": "Sprint 3 - Analytics & Polish", "due": "2026-11-17",
        "description": "4 Nov - 17 Nov: stats dashboard, file upload, text-to-speech, docs"},
}

PRIORITY_LABEL = {"Must have": "must-have", "Should have": "should-have", "Could have": "could-have"}

STORIES = [
    {
        "title": "US-01: Translate text", "sprint": 1, "priority": "Must have", "points": 5,
        "labels": ["feature", "backend", "ui"],
        "story": "As a user, I want to enter text and choose a target language, so that I can read it in that language.",
        "criteria": [
            "Form has a text area, a source-language dropdown (with 'Auto-detect') and a target-language dropdown",
            "Submitting shows the translation next to the input, and the input stays filled",
            "Text up to 5,000 characters is translated in a single request",
        ],
        "notes": "services/languages.py, services/engine.py (deep-translator GoogleTranslator), forms.py, views.py, translate.html",
    },
    {
        "title": "US-02: Auto-detect source language", "sprint": 1, "priority": "Must have", "points": 3,
        "labels": ["feature", "backend"],
        "story": "As a user, I want the source language to be detected automatically, so that I don't need to know which language the text is in.",
        "criteria": [
            "When 'Auto-detect' is selected, the detected language name is shown (e.g. 'Detected: French')",
            "Very short or ambiguous text falls back to the translator's own auto mode, with a note to the user",
        ],
        "notes": "services/detection.py using langdetect (seeded for repeatable results)",
    },
    {
        "title": "US-03: Save translation history", "sprint": 1, "priority": "Must have", "points": 3,
        "labels": ["feature", "backend"],
        "story": "As a user, I want every translation to be saved, so that I can come back to it later.",
        "criteria": [
            "A successful translation creates a database row (source text, translated text, languages, auto-detected flag, character count, engine, origin, timestamp)",
            "Failed translations are not saved",
            "Translations are visible in the Django admin",
        ],
        "notes": "models.py (Translation), migrations, admin.py",
    },
    {
        "title": "US-04: View translation history", "sprint": 2, "priority": "Must have", "points": 3,
        "labels": ["feature", "ui"],
        "story": "As a user, I want to see a list of my past translations, so that I can reuse them.",
        "criteria": [
            "History is listed newest first, 10 per page, with languages, a text preview and a timestamp",
            "An empty history shows a friendly empty state",
        ],
        "notes": "ListView-style view with Paginator, history.html",
    },
    {
        "title": "US-05: Search and filter history", "sprint": 2, "priority": "Should have", "points": 3,
        "labels": ["feature", "backend", "ui"],
        "story": "As a user, I want to search and filter my history, so that I can find a specific translation quickly.",
        "criteria": [
            "Keyword search matches source and translated text (case-insensitive)",
            "Filters for source language, target language and date range can be combined",
            "Filters are kept when moving between pages",
        ],
        "notes": "Q objects with icontains, GET-based filter form",
    },
    {
        "title": "US-06: Delete history entries", "sprint": 2, "priority": "Should have", "points": 2,
        "labels": ["feature", "backend"],
        "story": "As a user, I want to delete history entries, so that I can remove mistakes or private text.",
        "criteria": [
            "Each row has a delete button with a confirmation step",
            "A 'Clear all' option exists, also with confirmation",
            "Deletes only happen through POST requests (never GET)",
        ],
        "notes": "POST-only views, CSRF protection, Django messages",
    },
    {
        "title": "US-07: Friendly error handling", "sprint": 1, "priority": "Must have", "points": 3,
        "labels": ["feature", "backend"],
        "story": "As a user, I want clear error messages, so that I understand what went wrong and what to do next.",
        "criteria": [
            "Separate messages for: empty input, unsupported language, same source and target, no internet, API error/timeout",
            "No Django traceback is ever shown to the user; errors are logged",
            "If the primary engine fails, the app retries once with the fallback engine (MyMemory)",
        ],
        "notes": "exceptions.py (custom exception hierarchy), try/except in engine.py, logging",
    },
    {
        "title": "US-08: Statistics dashboard", "sprint": 3, "priority": "Should have", "points": 5,
        "labels": ["feature", "backend", "ui"],
        "story": "As a user, I want to see statistics about my translations, so that I understand my usage patterns.",
        "criteria": [
            "Charts: top 5 language pairs (bar), translations per day for the last 14 days (line), target-language share",
            "NumPy summary: total translations, mean / median / 90th-percentile text length",
            "A message is shown when there is not enough data yet",
        ],
        "notes": "services/analytics.py: QuerySet -> Pandas DataFrame, NumPy stats, Matplotlib (Agg backend) -> base64 PNG",
    },
    {
        "title": "US-09: Command-line translator", "sprint": 2, "priority": "Should have", "points": 3,
        "labels": ["feature", "backend"],
        "story": "As a power user, I want to translate from the terminal, so that I don't have to open a browser.",
        "criteria": [
            "`python cli.py \"Hello\" -t hi` works; options --source, --file, --list-langs, --no-save",
            "Running with no text starts an interactive input() mode",
            "CLI translations are saved to the same history with origin 'cli'",
            "Invalid usage exits with a non-zero code and a clear message",
        ],
        "notes": "argparse, sys.exit codes, django.setup() to reuse the ORM",
    },
    {
        "title": "US-10: Translate a .txt file", "sprint": 3, "priority": "Could have", "points": 5,
        "labels": ["feature", "backend", "ui"],
        "story": "As a user, I want to upload a .txt file, so that I can translate long documents.",
        "criteria": [
            "Only .txt files up to 1 MB are accepted, decoded as UTF-8",
            "Long text is translated in chunks (generator) and joined back together",
            "The translated result can be downloaded as a .txt file",
        ],
        "notes": "services/chunking.py generator (<= 5000 chars per chunk, split on sentence/line boundaries)",
    },
    {
        "title": "US-11: Text-to-speech for output", "sprint": 3, "priority": "Could have", "points": 2,
        "labels": ["feature", "ui"],
        "story": "As a user, I want to hear the translated text spoken aloud, so that I can learn the pronunciation.",
        "criteria": [
            "A speaker button reads the output in the target language",
            "The button is hidden or disabled if the browser or language isn't supported",
        ],
        "notes": "Browser Web Speech API or gTTS (decide in Sprint 3)",
    },
    {
        "title": "US-12: Project documentation", "sprint": 3, "priority": "Must have", "points": 2,
        "labels": ["docs"],
        "story": "As an evaluator, I want a clear README, so that I can set up and assess the project quickly.",
        "criteria": [
            "README covers overview, features, tech stack, setup (SQLite and MySQL), usage, screenshots and author",
            "README includes the final ITL-V syllabus mapping table",
        ],
        "notes": "Screenshots go in docs/screenshots/",
    },
]

CHORES = [
    {
        "title": "Chore: Django project setup", "sprint": 1, "labels": ["chore", "backend"],
        "body": (
            "### Task\nCreate the Django project skeleton so feature work can start.\n\n"
            "### Checklist\n"
            "- [ ] `translator_project` project and `translator` app created\n"
            "- [ ] Settings read from `.env` (secret key, debug, database)\n"
            "- [ ] SQLite / MySQL switch via `DB_ENGINE`\n"
            "- [ ] Base template with Bootstrap 5 and a navbar\n"
            "- [ ] `python manage.py runserver` shows a home page\n"
        ),
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DRY_RUN = False


def gh(*args, fatal=True):
    """Run a gh command and return its stdout as text.

    fatal=True  -> stop the whole script if the command fails
    fatal=False -> print a warning and carry on
    """
    cmd = ["gh", *args]
    if DRY_RUN:
        print("  [dry-run]", " ".join(a if " " not in a else f'"{a}"' for a in cmd[:8]), "..." if len(cmd) > 8 else "")
        return ""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        sys.exit("ERROR: 'gh' not found. Install GitHub CLI from https://cli.github.com and run 'gh auth login'.")
    if result.returncode != 0:
        message = f"gh {' '.join(args[:3])} ...\n{result.stderr.strip()}"
        if fatal:
            sys.exit(f"ERROR running: {message}")
        print(f"  WARNING: {message}")
        return ""
    return result.stdout.strip()


def story_body(s):
    """Build the issue body in the same layout as the user_story.yml template."""
    criteria = "\n".join(f"- [ ] {c}" for c in s["criteria"])
    return (
        f"### User story\n{s['story']}\n\n"
        f"### Acceptance criteria\n{criteria}\n\n"
        f"### Priority (MoSCoW)\n{s['priority']}\n\n"
        f"### Story points\n{s['points']}\n\n"
        f"### Technical notes\n{s['notes']}\n"
    )


# ---------------------------------------------------------------------------
# Step 1: labels, milestones, issues
# ---------------------------------------------------------------------------

def create_labels():
    print("\n== Labels ==")
    for name, color, desc in LABELS:
        gh("label", "create", name, "--color", color, "--description", desc, "--force")
        print(f"  ok  {name}")


def create_milestones():
    print("\n== Milestones ==")
    existing = set(gh("api", "repos/{owner}/{repo}/milestones?state=all", "--jq", ".[].title").splitlines())
    for sprint in SPRINTS.values():
        if sprint["title"] in existing:
            print(f"  skip {sprint['title']} (exists)")
            continue
        gh("api", "repos/{owner}/{repo}/milestones",
           "-f", f"title={sprint['title']}",
           "-f", f"description={sprint['description']}",
           "-f", f"due_on={sprint['due']}T23:59:59Z")
        print(f"  ok  {sprint['title']}")


def create_issues():
    print("\n== Issues ==")
    existing = set(gh("issue", "list", "--state", "all", "--limit", "200",
                      "--json", "title", "--jq", ".[].title").splitlines())

    for s in STORIES:
        if s["title"] in existing:
            print(f"  skip {s['title']} (exists)")
            continue
        labels = ["user-story", PRIORITY_LABEL[s["priority"]], *s["labels"]]
        label_args = [arg for label in labels for arg in ("--label", label)]
        url = gh("issue", "create", "--title", s["title"], "--body", story_body(s),
                 "--milestone", SPRINTS[s["sprint"]]["title"], *label_args)
        print(f"  ok  {s['title']}  {url}")

    for c in CHORES:
        if c["title"] in existing:
            print(f"  skip {c['title']} (exists)")
            continue
        label_args = [arg for label in c["labels"] for arg in ("--label", label)]
        url = gh("issue", "create", "--title", c["title"], "--body", c["body"],
                 "--milestone", SPRINTS[c["sprint"]]["title"], *label_args)
        print(f"  ok  {c['title']}  {url}")


# ---------------------------------------------------------------------------
# Step 2: add issues to the Project (v2) board
# ---------------------------------------------------------------------------

def ensure_field(project, fields, name, *extra):
    """Create a custom project field if it doesn't exist yet. Returns the field dict."""
    if name not in fields:
        gh("project", "field-create", str(project), "--owner", "@me", "--name", name, *extra)
        print(f"  ok  created field '{name}'")
        fields.update(load_fields(project))
    return fields.get(name, {})


def load_fields(project):
    raw = gh("project", "field-list", str(project), "--owner", "@me", "--format", "json")
    return {f["name"]: f for f in json.loads(raw)["fields"]} if raw else {}


def setup_project(project):
    print(f"\n== Project board #{project} ==")
    repo = gh("repo", "view", "--json", "name", "--jq", ".name")
    # Linking makes the board appear on the repo's "Projects" tab (warns if already linked)
    gh("project", "link", str(project), "--owner", "@me", "--repo", repo, fatal=False)
    print(f"  ok  linked repo '{repo}'")

    project_id = gh("project", "view", str(project), "--owner", "@me", "--format", "json", "--jq", ".id")
    fields = load_fields(project)

    points_field = ensure_field(project, fields, "Story Points", "--data-type", "NUMBER")
    priority_field = ensure_field(project, fields, "Priority", "--data-type", "SINGLE_SELECT",
                                  "--single-select-options", "Must have,Should have,Could have")
    status_field = fields.get("Status", {})

    # Look up option ids for single-select fields by their visible name
    status_opts = {o["name"]: o["id"] for o in status_field.get("options", [])}
    priority_opts = {o["name"]: o["id"] for o in priority_field.get("options", [])}
    if not DRY_RUN and "Backlog" not in status_opts:
        sys.exit("ERROR: the board's Status field has no 'Backlog' option.\n"
                 "Rename/add the Status options in the board settings first (see the setup guide).")

    issues = json.loads(gh("issue", "list", "--state", "all", "--limit", "200",
                           "--json", "title,url") or "[]")
    by_title = {i["title"]: i["url"] for i in issues}
    stories = {s["title"]: s for s in STORIES}

    for title in [*stories, *(c["title"] for c in CHORES)]:
        url = by_title.get(title)
        if not url and not DRY_RUN:
            print(f"  skip {title} (issue not found, run step 1 first)")
            continue
        item_id = gh("project", "item-add", str(project), "--owner", "@me",
                     "--url", url or "<url>", "--format", "json", "--jq", ".id")

        def edit(field, *value):
            gh("project", "item-edit", "--id", item_id, "--project-id", project_id,
               "--field-id", field.get("id", "<field>"), *value)

        edit(status_field, "--single-select-option-id", status_opts.get("Backlog", "<opt>"))
        if title in stories:
            s = stories[title]
            edit(points_field, "--number", str(s["points"]))
            edit(priority_field, "--single-select-option-id", priority_opts.get(s["priority"], "<opt>"))
        print(f"  ok  {title}")


# ---------------------------------------------------------------------------

def main():
    global DRY_RUN
    parser = argparse.ArgumentParser(description="Create labels, milestones, issues and fill the Kanban board.")
    parser.add_argument("--project", type=int, help="Project number (from the board URL) to add the issues to")
    parser.add_argument("--dry-run", action="store_true", help="Print the gh commands without running them")
    args = parser.parse_args()
    DRY_RUN = args.dry_run

    if args.project:
        setup_project(args.project)
    else:
        create_labels()
        create_milestones()
        create_issues()
        print("\nDone. Next: create the Project board, then run with --project <number>.")


if __name__ == "__main__":
    main()
