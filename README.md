# domain‑paths‑crawler

A simple Django web crawler to discover and record paths under a domain.  

https://github.com/user-attachments/assets/fa9cdbc0-20e5-4fa7-9984-e733961379c1

---

## Table of Contents

- [Features](#features)  
- [Getting Started](#getting-started)  
  - [Prerequisites](#prerequisites)  
  - [Installation](#installation)  
  - [Running](#running)
  - [Testing](#testing)

---

## Features

- Crawl all accessible paths under a given domain by user input
- Crawling is completed asynchronously using Celery distributed task queues
- Store discovered paths in a SQLite database  
- Uses Django to manage and visualize crawled data  

---

## Getting Started

### Prerequisites

- Python 3.8+  
- pip  
- (Optional) virtualenv

### Installation

```bash
# Clone the repository
git clone https://github.com/WasifButt/domain-paths-crawler.git
cd domain-paths-crawler

# (Optional) Create & activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
brew install rabbitmq
```

### Running

```bash
python manage.py makemigrations
python manage.py migrate

# From a different shell begin the celery worker
brew services start rabbitmq
celery -A webcrawler worker --loglevel=info

# Run the django server
python manage.py runserver
```
The app can then be accessed from http://127.0.0.1:8000/

### Testing

```bash
python manage.py test
```

