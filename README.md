# Basira - Intelligent Web Scraping & AI Insights Platform

Basira is an enterprise-grade web service designed for automated data extraction, structured archiving, and high-fidelity AI analysis. Built as a capstone project, it leverages the **Gemini 2.5 Flash** engine to transform raw web data into strategic e-commerce intelligence and academic research synthesis.

---

## Key Features

### 1. E-Commerce Intelligence Dashboard (Core)
* **Targeted Extraction:** Automated scraping of product prices, ratings, and high-resolution images from major platforms like Dumyah and Matalan.
* **Real-time Progress Monitoring:** A dynamic, color-coded alert system that tracks scraping jobs in real-time with states for **Running** (blue), **Success** (green), and **Error** (red).
* **Market Analysis Suite:** High-contrast, multi-shade purple visual dashboards powered by **Chart.js** for price distribution and trend analysis.
* **Enterprise Scaling:** A UI designed with large typography (titles up to 3.5rem) and significant whitespace for maximum readability.
* **Format-Agnostic Export:** One-click downloads for datasets in structured CSV or JSON formats.

### 2. Research Archive ETL (archive_etl)
* **Longitudinal Pipeline:** Automated harvesting and archiving of news articles from regional sources (e.g., Jordan News, Ammon News).
* **Multi-lingual Cleaning:** Intelligent extraction of English and Arabic content with automatic URL bypass for legacy structures.
* **Thematic AI Synthesis:** Uses Google Gemini to generate thematic summaries, identify narrative shifts, and determine article sentiment.

### 3. AI Consultant Chatbot (chatbot)
* **Knowledge Base Integration:** Upload PDF research documents to provide direct context to the AI advisor.
* **MENA Market Expertise:** Specialized system instructions for marketing strategy and digital transformation within the Middle Eastern market.
* **Voice Interface:** Integrated web speech recognition and text-to-speech for hands-free strategic consultation.
* **Modern UI:** A sidebar-driven interface with full session history management and high-fidelity components.

---

## Tech Stack

* **Backend:** Django 5.0 (Python)
* **Task Management:** Celery + Redis (Asynchronous processing)
* **Scraping Engine (Hybrid):** * **Playwright:** Primary engine for E-commerce scraping (using Chromium).
    * **Selenium + Selenium Stealth:** Specialized engine for Research Archive/News harvesting.
* **Generative AI:** Google Gemini 2.5 Flash (Dynamic selector detection & thematic synthesis).
* **Frontend:** HTML5, CSS3 (Enterprise Scale), Bootstrap 5, Chart.js.
* **Database:** SQLite (Development) / PostgreSQL (Production)

---

## Prerequisites

* **Python 3.10+**
* **Docker Desktop** (For running the Redis message broker)
* **Google Chrome** (Installed on host machine for Selenium drivers)
* **Playwright Browsers:** Chromium (Installed via `playwright install`)
* **Git**

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/Malek-Qaraleh/Basira.git](https://github.com/Malek-Qaraleh/Basira.git)
cd webscraper


2. Create a Virtual Environment

It is recommended to use a virtual environment to manage dependencies.

Windows:
```console
python -m venv .venv
.venv\Scripts\activate
```

Mac/Linux:

```console
python3 -m venv .venv
source .venv/bin/activate
```

3. Install Dependencies
```console
pip install -r requirements.txt
```

4. Initialize the Database

Run the migrations to set up your database schema.

python manage.py makemigrations
python manage.py migrate


5. Create a Superuser

You need an admin account to access the Django Admin interface.
```console
python manage.py createsuperuser
```

## Running the Application

To run Basira, you need to run three separate processes simultaneously (use separate terminals).

Terminal 1: Infrastructure (Redis)

Start the Redis container for the task queue.
```console
docker run -d -p 6379:6379 redis
```

Terminal 2: Background Worker (Celery)

This process handles the heavy lifting (scraping and AI analysis).
Windows:
```console
celery -A webscraper worker --loglevel=info --pool=solo
```

Mac/Linux:
```console
celery -A webscraper worker --loglevel=info
```

Terminal 3: Web Server (Django)

Start the user interface.
```console
python manage.py runserver
```

Access the application at: http://127.0.0.1:8000/

## Usage Guide

Setting up News Sources (Admin)

Before using the Research tool, you must configure the news sources in the admin panel.

Go to http://127.0.0.1:8000/admin/

Under Basira Research Archive, add a Scrape Source.

Name: Jordan News | URL: https://jordannews.jo/ | Start URL: https://jordannews.jo/archive.xml | Lang: en

Name: Ammon News (English) | URL: http://en.ammonnews.net/ | Start URL: http://en.ammonnews.net/ | Lang: en

### Using the Research Tool

Navigate to "Research Articles" in the navbar.

Enter a Topic (e.g., "Water Scarcity") and a Target URL (e.g., a search result page from Jordan News or Ammon News (https://jordannews.jo/AdvancedSearch/water)).

Set the Article Limit (e.g., 10 or 25).

Click Start Pipeline. The Celery worker will scrape the data and the AI will analyze it.

Refresh to see the status change to Completed and view the results.

### Using the E-Commerce Scraper

Navigate to "New Scrape".

Paste a category URL from a supported site (e.g., Matalan or Dumyah).

The system will scrape products, prices, and images in the background.

View the Dashboard for price distribution charts and AI insights.

## The Team

Malek Al-Qaraleh

Rama Al-Majali

Firas Balloul
