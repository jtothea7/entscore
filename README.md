---
title: EntScore
emoji: 🎯
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# EntScore

SEO page optimization tool that analyzes your page against top-ranking competitors and generates actionable optimization briefs.

## What It Does

1. Takes your page URL + target keyword
2. Fetches top 10 SERP competitors via DataForSEO
3. Scrapes and analyzes all pages for entity coverage, writing style, and structure
4. Identifies what's missing or weak on your page vs competitors
5. Generates a comprehensive optimization brief ready to paste into Claude for rewriting

## Setup

```bash
# 1. Run the install script
chmod +x setup.sh
./setup.sh

# 2. Add your DataForSEO credentials
cp .env.example .env
# Edit .env with your credentials

# 3. Activate the virtual environment
source venv/bin/activate

# 4. Run the app
streamlit run app.py
```

## DataForSEO

You need a DataForSEO account ($50 minimum). Get credentials at https://dataforseo.com/dashboard

Each analysis costs approximately $0.02-0.10 depending on the number of API calls.

## Features

- **Entity Gap Analysis** — finds semantic concepts competitors mention but you don't
- **Health Score** — weighted score (entity coverage 40%, headings 20%, word count 20%, readability 10%, links 10%)
- **Priority Actions** — ranked list of what to fix first
- **Writing Style Analysis** — formality score and style markers
- **GSC Audit Queue** — upload GSC data to find your biggest optimization opportunities
- **Optimization Brief** — ready-to-use brief for content rewriting
- **Before/After Comparison** — track score improvements over time

## Tech Stack

- **Frontend:** Streamlit
- **NLP:** spaCy (en_core_web_trf) + KeyBERT + sentence-transformers
- **SEO Data:** DataForSEO API (only paid dependency)
- **Database:** SQLite (local, WAL mode)
- **Scraping:** trafilatura + BeautifulSoup
