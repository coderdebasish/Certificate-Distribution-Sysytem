# Certificate Distribution Management System (CDMS)

> A production-grade desktop application that fully automates certificate distribution for events — workshops, hackathons, seminars, webinars, and more.

---

## The Problem

Event organizers waste hours on repetitive manual work:

```
Export 500 PDFs named 1.pdf, 2.pdf, 3.pdf...
       ↓
Rename every file manually
       ↓
Prepare Excel sheet
       ↓
Search certificate → Attach → Write email → Repeat × 500
       ↓
Hope nothing goes wrong.
```

**CDMS eliminates this entirely.**

---

## What It Does

| Feature | Description |
|---|---|
| **Auto Certificate Renaming** | Extracts participant names from PDFs using text extraction or OCR |
| **Participant Management** | Import from Excel or enter manually, with full validation |
| **Intelligent Matching** | Fuzzy-matches participants to their certificates automatically |
| **Email Templates** | Write one template with `{name}` placeholders — generates 500 personalized emails |
| **Bulk Email Sending** | Queue-based Gmail sending with pause, resume, and crash recovery |
| **Full Audit Trail** | Reports, history, and delivery proof for every operation |

---

## Core Principle

> **The software must NEVER send an incorrect certificate to a participant.**
>
> Every suspicious condition stops the process and notifies the user. Accuracy > Speed.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| GUI Framework | CustomTkinter |
| Database | SQLite |
| PDF Reading | PyMuPDF + pdfplumber |
| OCR | PaddleOCR |
| Email | Gmail (SMTP via App Password) |
| Name Matching | rapidfuzz |
| Reports | reportlab + XlsxWriter |
| Encryption | cryptography |

---

## Project Workflow

```
Create Project → Import Certificates → Analyze & Rename → Verify
       ↓
Import Participants → Certificate Matching → Review Matches
       ↓
Prepare Email Template → Preview Emails → Configure Gmail
       ↓
Send Certificates → Generate Reports → Archive Project
```

---

## Project Structure

```
app/
├── config/          Configuration, constants, settings
├── models/          Data models (Project, Participant, Certificate, etc.)
├── database/        SQLite connection, migrations, repositories
├── services/
│   ├── ocr/         PDF text extraction + PaddleOCR engine
│   ├── email/       Gmail provider + email queue manager
│   ├── matching/    Fuzzy name matching engine
│   ├── reports/     PDF/Excel/CSV report generation
│   └── placeholder/ Email template placeholder engine
├── workers/         Background thread workers (non-blocking)
├── utils/           File ops, validators, crypto, logger
├── ui/
│   ├── components/  Reusable widgets (table, sidebar, dialogs, etc.)
│   └── modules/     Screen views (dashboard, rename, participants, etc.)
└── assets/          Icons, fonts
main.py              Application entry point
```

---

## Installation

### Prerequisites

- Python 3.11 or newer
- Windows 10 / 11

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/certificate-distribution-system.git
cd certificate-distribution-system

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

---

## Gmail Setup

CDMS uses **Gmail App Passwords** — not your Google account password.

1. Enable 2-Factor Authentication on your Google account
2. Go to Google Account → Security → App Passwords
3. Generate a password for "Mail" on "Windows Computer"
4. Enter it in CDMS Settings → Email

Your credentials are encrypted locally and never transmitted anywhere.

---

## Screenshots

> *Coming soon*

---

## Roadmap

| Version | Planned Features |
|---|---|
| v1.0 | Desktop, Gmail, OCR, SQLite, Projects |
| v2.0 | Outlook, Resend, Google Sheets, Multiple Attachments |
| v3.0 | Cloud Sync, Team Collaboration, Email Scheduling |
| v4.0 | Web Application, Mobile Companion, Certificate Verification Portal |

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
