# Basira - Intelligent Web Scraping & Data Analysis Platform

Basira is a comprehensive web service designed for automated data extraction, structured archiving, and AI-powered analysis. Built as a capstone project, it integrates advanced web scraping techniques with Generative AI to provide actionable insights for e-commerce and academic research.


## 🚀 Key Features

1. E-Commerce Scraper (core)

Targeted Scraping: Automated extraction of product data (prices, ratings, images) from supported sites like Dumyah and Matalan.

Market Analysis: Visual dashboards for price distribution and product comparisons.

Export: Download datasets in CSV or JSON formats.

2. Research Archive ETL (archive_etl)

Longitudinal Data: Automated pipeline to harvest and archive news articles from sources like Jordan News and Ammon News.

Smart Extraction: Handles English and Arabic content, bypasses legacy URL structures, and cleans article text.

Thematic Analysis: Uses Google Gemini AI to generate summaries, identify key themes, and determine narrative tone for collected articles.

3. AI Consultant Chatbot (chatbot)

Interactive Advisor: A built-in chatbot to discuss data trends, marketing strategies, and research methodologies.

Unified Interface: Modern chat UI with history management.

## 🛠️ Tech Stack

Backend: Django 5.0 (Python)

Task Queue: Celery + Redis

Scraping: Selenium + Selenium Stealth (Headless Chrome)

Database: SQLite (Default) / PostgreSQL (Production ready)

AI Engine: Google Gemini Pro

Frontend: HTML5, CSS3, Bootstrap 5, Chart.js

Containerization: Docker (for Redis)

## ⚙️ Prerequisites

Python 3.10+

Docker Desktop (for running Redis)

Google Chrome (installed on the host machine for Selenium)

Git

## 📥 Installation & Setup

1. Clone the Repository

```console
git clone [https://github.com/Malek-Qaraleh/Basira.git](https://github.com/Malek-Qaraleh/Basira.git)
cd Basira
```


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

## 🚀 Running the Application

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

## 📖 Usage Guide

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

## 👥 The Team

Malek Al-Qaraleh

Rama Al-Majali

Firas Balloul
