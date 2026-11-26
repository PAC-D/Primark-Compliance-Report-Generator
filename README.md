# Primark Compliance Report Generator

PAC-D's monthly Primark packaging-management compliance reporting: ingest
bi-weekly transaction exports into PostgreSQL, explore the month in a web
dashboard, and generate per-supplier compliance PDFs, an Excel summary
workbook, a KPI report and raw-data extracts.

## Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Tech Stack](#tech-stack)
- [Run locally](#run-locally)
- [Server setup (one time)](#server-setup-one-time)
- [Releasing](#releasing)
- [Usage](#usage)
- [Testing](#testing)
- [Data & Confidentiality](#data--confidentiality)

## Overview

Two containers behind the host's nginx:

- `web`: the Next.js dashboard (six tabs: Dashboard, Supplier Compliance, KPI,
  Reports, Data and Suppliers), served under `/compliance`.
- `api`: FastAPI over the `tps` Python package (metrics, report rendering with
  headless Chromium, ingest). Long jobs run one at a time in the background.

nginx puts HTTP basic auth in front of both and routes `/compliance/api/` to
the API and `/compliance/` to the page.

## Repository Structure

```
.
├── api/                  # FastAPI app (main.py, routes.py) and its Dockerfile
├── web/                  # Next.js app (standalone build) and its Dockerfile
├── tps/                  # Python package: db, ingest, metrics, reports, jobs, actions, extract
├── deploy/               # nginx-compliance.conf, release.sh
├── tests/                # pytest suite (web/ has its own vitest suite)
├── docker-compose.yml    # api on 127.0.0.1:8602, web on 127.0.0.1:8601
├── .env.example          # Server settings; copy to .env
├── config.yaml.example   # Local-only database settings (no Docker)
└── requirements.txt
```

`output/` (a Docker volume on the server) has one folder per reporting month:

```
2026_August/
  Supplier_Reports/BD_Region/*.pdf, CN_Region/*.pdf
  Supplier_Data/BD_Region/*.xlsx, CN_Region/*.xlsx, All_Suppliers_Aug_2026.xlsx
  Summary_Report_August_2026.xlsx
  KPI_Report_August_2026.pdf
```

## Tech Stack

| Layer         | Technology                                   |
|---------------|----------------------------------------------|
| Dashboard     | Next.js 16, React 19, Tailwind 4             |
| API           | FastAPI, uvicorn                             |
| ETL / metrics | pandas, openpyxl                             |
| Database      | PostgreSQL via SQLAlchemy                    |
| PDF rendering | Jinja2 + Playwright (headless Chromium)      |
| Deploy        | Docker Compose, host nginx + certbot         |
| Tests         | pytest, vitest                               |

## Run locally

Requirements: Python 3.11+, Node 22+, a PostgreSQL database you can reach.

```bash
pip install -r requirements.txt
playwright install chromium
cp config.yaml.example config.yaml     # database settings (or set DB_* variables)
python -c "from tps.db import init_db; init_db()"
uvicorn api.main:app --port 8000
```

In a second terminal: `npm --prefix web install`, then `npm --prefix web run dev`
and open <http://localhost:3000/compliance>. In development the page proxies
`/api` to port 8000; set `ALLOWED_ORIGINS=http://localhost:3000` (the default)
for uploads and other POSTs.

The Docker setup (`docker compose up --build`) is meant for the server: the
`web` container only reaches the API through nginx's `/compliance/api/` route,
so the page does not work from `http://localhost:8601` alone. The API's own
health check does: <http://localhost:8602/api/health> returns `{"ok":true}`.

## Server setup (one time)

Server: `ubuntu@65.2.228.79`, projects under `/srv/primark-projects/`. Steps
that touch the server or AWS are run by a person, not by automation.

1. **Database.** On `database-1` (RDS), as the admin user:
   ```sql
   CREATE DATABASE tps_compliance;
   CREATE USER tps_compliance WITH PASSWORD '<strong password>';
   GRANT ALL PRIVILEGES ON DATABASE tps_compliance TO tps_compliance;
   \c tps_compliance
   GRANT ALL ON SCHEMA public TO tps_compliance;
   ```
2. **Clone.**
   ```bash
   cd /srv/primark-projects
   git clone https://github.com/PAC-D/Primark-Compliance-Report-Generator.git
   cd Primark-Compliance-Report-Generator
   ```
3. **`.env`.** `cp .env.example .env`, fill in `DB_HOST`
   (`database-1.ch4qkgwmwuqn.ap-south-1.rds.amazonaws.com`) and `DB_PASSWORD`,
   keep `DB_SSLMODE=require` and `ALLOWED_ORIGINS=https://primark.pac-d.com`,
   then `chmod 600 .env`.
4. **Tables.** From the clone folder, build the image and create the tables:
   ```bash
   docker compose build api
   docker compose run --rm api python -c "from tps.db import init_db; init_db()"
   ```
   Only on a fresh database; never re-run it, it drops `raw_data`.
5. **Login.** `sudo htpasswd -c /etc/nginx/tps-compliance.htpasswd team`
   (`apache2-utils` provides `htpasswd`).
6. **nginx.** In the 443 `server` block of `/etc/nginx/sites-enabled/primark`
   add
   `include /srv/primark-projects/Primark-Compliance-Report-Generator/deploy/nginx-compliance.conf;`
   then `sudo nginx -t && sudo systemctl reload nginx`. The
   `primark.pac-d.com` certificate already exists on the server (certbot); no
   new certificate is needed.
7. **First release.** `docker compose up -d --build` on the server (or run the
   release script from your PC, below).
8. **Load data.** Open the Data page and upload the January-October 2026
   transaction files.
9. **Public address.** <https://primark.pac-d.com/compliance> works once
   `primark.pac-d.com` is detached from Carton Connect's CloudFront and points
   at this server.

The API and web ports are bound to `127.0.0.1` only (8602 and 8601, next to
the existing containers on 8501-8502); nginx is the only way in.

## Testing on the server before the DNS change

Reach the server's nginx through an SSH tunnel and a hosts entry (nginx matches
`server_name primark.pac-d.com`, and the certificate is valid for that name):

1. Tunnel: `ssh -i <key> -L 8443:127.0.0.1:443 ubuntu@65.2.228.79`
2. Hosts entry (as admin; `/etc/hosts` or `C:\Windows\System32\drivers\etc\hosts`):
   `127.0.0.1 primark.pac-d.com`
3. Browse <https://primark.pac-d.com:8443/compliance/>.
4. The browser now sends `Origin: https://primark.pac-d.com:8443`, so POSTs are
   refused until you add it to `ALLOWED_ORIGINS` in the server's `.env`
   (comma-separated, after the existing value) and run `docker compose up -d`.

After the DNS change, remove that origin from `.env` (and `docker compose up -d`
again) and delete the hosts entry.

## Releasing

Push the branch to deploy, then from your PC:

```bash
export TPS_SSH_KEY=~/.ssh/<key>.pem      # optional; TPS_SSH defaults to ubuntu@65.2.228.79
bash deploy/release.sh
```

It pulls (fast-forward only), rebuilds, restarts and checks `/api/health` and
the web container on the server; it exits non-zero if any step fails.

`docker compose build` runs `next build` on the server, which needs about 1 GB
of free memory while it builds.

`/app/logs` is inside the container, so the Recent log on the Reports page
resets on each release.

Memory: with `PDF_WORKERS=2`, an all-supplier August 2026 PDF job peaked at
1.7 GiB in `docker stats` (api 1.67 GiB, web 55 MiB), under the 2 GB budget. Each PDF thread restarts its Chromium every 10 reports (`RECYCLE_AFTER` in `tps/reports/pdf.py`), because a reused page otherwise grows to about 2.5 GiB over 127 reports.

### Upgrading from a root image

If the `tps-output` volume was created by an image that ran as root, every job
fails with "Permission denied" after switching to the `pwuser` image. Fix the
ownership once (keeps the generated reports):

```bash
docker compose run --rm -u root api chown -R pwuser:pwuser /app/output
```

`docker volume ls` shows the volume, prefixed with the project folder name
(for example `primark-compliance-report-generator_tps-output`).

## Usage

| Page | What it does |
|------|--------------|
| Dashboard | The month's summary workbook on screen: headline figures, charts and sheets (top performers, follow-up required, visibility), the yearly view, and the all-supplier table with filters and bulk PDF / data downloads. Download the workbook itself from here. |
| Supplier Compliance | One supplier's PDF on screen, found by searching supplier or factory name; with none chosen, the suppliers needing follow-up. Download its PDF or data. |
| KPI | Regional and trend KPIs across all suppliers; Download KPI report. |
| Reports | Run Supplier Reports, Summary Workbook, KPI Report, Supplier Data and All Supplier Data for a month; shows what exists and when it was generated. One job at a time, with progress and Cancel. |
| Data | Upload bi-weekly exports (files already loaded are skipped unless re-load is ticked; re-loading replaces a file's rows), or clear the database. |
| Suppliers | Every supplier with its emails: edit in place, import or export a "Supplier Name / Email" workbook. |

Regions: Bangladesh, India, Pakistan, Sri Lanka, Morocco and Turkey are BD;
every other country is CN; a supplier with countries from both is CN.

Settings (environment): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_SSLMODE`, `OUTPUT_DIR`, `PDF_WORKERS` (default 2; blank, non-numeric or below 1 also gives 2),
`ALLOWED_ORIGINS` (comma-separated; POSTs from other origins are refused).

## Testing

```bash
pytest -q
cd web && npx vitest run && npm run build
```

The pytest suite never touches the database or `output/`. The summary-workbook
content tests compare against `tests/fixtures/reference_july_2026.xlsx`, which
holds real supplier data and is not in git; they skip when it is absent.

## Data & Confidentiality

This tool works on real Primark supplier and packaging-compliance data.
`.gitignore` keeps all of it out of version control: `data/`, `output/`,
`logs/`, `config.yaml`, `.env` (database credentials) and `tests/fixtures/`.

## License

Proprietary — internal PAC-D project built for Primark. All rights reserved.
