# 🌐 Python Language Translator

A Django web app (with a companion command-line tool) that translates text between 100+ languages, **auto-detects the source language**, keeps a searchable **translation history** in a database, and shows **usage analytics** built with Pandas, NumPy and Matplotlib.

> **Course:** Information Technology Laboratory-V (ITL-V), B.Tech IT, Semester V
> **Institute:** Bharati Vidyapeeth College of Engineering, Pune
> **Type:** Project Based Learning (PBL), individual project
> **Faculty guide:** _[Prof. name]_
> **Submission deadline:** _[date]_

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Django](https://img.shields.io/badge/django-5.2%20LTS-green)

---

## Table of contents
- [Features](#features)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [Screenshots](#screenshots)
- [Project management](#project-management)
- [ITL-V syllabus mapping](#itl-v-syllabus-mapping)
- [Author](#author)

## Features

| | Feature | Status |
|---|---|---|
| 🔤 | Translate text between 100+ languages | ⏳ Planned |
| 🔍 | Auto-detect the source language | ⏳ Planned |
| 💾 | Save every translation to the database | ⏳ Planned |
| 📜 | History page with search, filters, pagination and delete | ⏳ Planned |
| 📊 | Analytics dashboard (top language pairs, daily usage, text-length stats) | ⏳ Planned |
| 🛡️ | Friendly error handling (no internet, empty input, API failure, automatic fallback engine) | ⏳ Planned |
| 💻 | Command-line translator (`cli.py`) that shares the same history | ⏳ Planned |
| 📄 | Upload a `.txt` file and download the translation | ⏳ Planned |
| 🔊 | Text-to-speech for the translated output | ⏳ Planned |

_(Status is updated as each user story is completed.)_

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.10+ | Course language |
| Web framework | Django 5.2 LTS | MVT architecture, ORM, admin, forms |
| Translation | [deep-translator](https://pypi.org/project/deep-translator/) (Google, MyMemory as fallback) | Free, no API key |
| Language detection | [langdetect](https://pypi.org/project/langdetect/) | Offline, tells us *which* language was detected |
| Database | MySQL (via PyMySQL) or SQLite | MySQL for the syllabus; SQLite for zero-setup development |
| Analysis | NumPy, Pandas | Statistics and grouping on translation history |
| Charts | Matplotlib | Server-side charts embedded in the stats page |
| UI | Django templates + Bootstrap 5 | Clean UI without a JS framework |

## Architecture

```
 Browser ──► urls.py ──► views.py ──► forms.py (validation)
                            │
                            ▼
              translator/services/   (plain Python, no Django)
              ├─ detection.py   langdetect
              ├─ engine.py      deep-translator + fallback
              ├─ chunking.py    generator for long text
              └─ analytics.py   Pandas / NumPy / Matplotlib
                            │
                            ▼
                 models.py ──► Django ORM ──► MySQL / SQLite
                            ▲
 cli.py (argparse) ─────────┘   reuses the same services + model
```

The translation logic sits in a **service layer** that doesn't depend on Django, so the web app and the CLI share one implementation and it can be unit-tested on its own.

## Project structure

```
python-language-translator/
├── .github/                 # issue templates + PR template
├── translator_project/      # Django project settings and root URLs
├── translator/              # Django app: models, views, forms, templates, services
├── scripts/                 # helper scripts (GitHub setup, raw SQL demo)
├── docs/screenshots/        # images used in this README
├── cli.py                   # command-line translator
├── manage.py
├── requirements.txt
└── .env.example             # template for local settings
```

## Setup

### Prerequisites
- Python 3.10 or newer
- Git
- _(Optional)_ MySQL 8.x. SQLite works without any setup.

### 1. Clone and create a virtual environment

**Windows (PowerShell)**
```powershell
git clone https://github.com/saksham7730/python-language-translator.git
cd python-language-translator
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS**
```bash
git clone https://github.com/saksham7730/python-language-translator.git
cd python-language-translator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure settings
```powershell
copy .env.example .env      # Linux/macOS: cp .env.example .env
```
Then edit `.env`. Leave `DB_ENGINE=sqlite` to start straight away.

### 3. _(Optional)_ Use MySQL
```sql
CREATE DATABASE translator_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Set `DB_ENGINE=mysql` and fill in `DB_USER` / `DB_PASSWORD` in `.env`.
`utf8mb4` is required so that scripts like Hindi, Chinese and emoji are stored correctly.

### 4. Create tables and run
```powershell
python manage.py migrate
python manage.py runserver
```
Open http://127.0.0.1:8000/

## Usage

_Details will be added as features are completed._

```powershell
# Web app
python manage.py runserver

# CLI (coming in Sprint 2)
python cli.py "Good morning" -t hi
python cli.py --list-langs
```

## Screenshots

| Page | Screenshot |
|---|---|
| Translate | _coming soon_ <!-- ![Translate](docs/screenshots/translate.png) --> |
| History | _coming soon_ <!-- ![History](docs/screenshots/history.png) --> |
| Statistics | _coming soon_ <!-- ![Stats](docs/screenshots/stats.png) --> |
| CLI | _coming soon_ <!-- ![CLI](docs/screenshots/cli.png) --> |

## Project management

This project follows an Agile workflow on GitHub:

- **User stories** are tracked as [GitHub Issues](https://github.com/saksham7730/python-language-translator/issues) with acceptance criteria, MoSCoW priority and story points.
- **Kanban board:** [GitHub Project](https://github.com/users/saksham7730/projects) with columns Backlog → To Do → In Progress → In Review → Done.
- **Sprints** are tracked as [Milestones](https://github.com/saksham7730/python-language-translator/milestones):

| Sprint | Dates (2026) | Goal |
|---|---|---|
| Sprint 1: Core Translation | 7 Oct – 20 Oct | Translate, auto-detect, save, error handling |
| Sprint 2: History & CLI | 21 Oct – 3 Nov | History page, search/filter, delete, CLI |
| Sprint 3: Analytics & Polish | 4 Nov – 17 Nov | Stats dashboard, file upload, TTS, docs |

- **Branching:** every story is built on a `feature/US-xx-short-name` branch and merged through a pull request that says `Closes #N`, which closes the issue and moves its card to **Done** automatically.

## ITL-V syllabus mapping

| Unit | Topic | Where it is used |
|---|---|---|
| 1 | Core Python, functions, user input, command-line arguments | `cli.py` (argparse, interactive `input()` mode) |
| 2 | Data types, iterators, generators, comprehensions, lambdas, exceptions | `services/chunking.py` (generator), `services/languages.py` (comprehensions, sets, tuples), `exceptions.py` |
| 3 | Databases with Python (DDL/DML) | `models.py` + migrations, `scripts/db_raw_sql.py` (raw SQL) |
| 4 | NumPy | `services/analytics.py` (mean, median, percentiles) |
| 5 | Pandas + Matplotlib | `services/analytics.py`, stats page charts |
| 6 | Django (MVT) | The whole web app |

_(This table will be finalised at the end of the project.)_

## Author

**Saksham**
B.Tech IT, Third Year, Bharati Vidyapeeth College of Engineering, Pune
GitHub: [@saksham7730](https://github.com/saksham7730)
