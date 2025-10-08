from celery import shared_task

from webcrawlerapp.service import WebCrawlerService

@shared_task
def run_web_crawler(domain: str):
    crawler = WebCrawlerService(domain=domain)
    crawler.run()