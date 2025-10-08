from collections import deque
from datetime import datetime
from urllib.parse import urlparse, urljoin
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

from webcrawlerapp.models import Domain, Path


class DomainModelService:
    @staticmethod
    def get_domain_id_by_name(domain: str) -> int:
        try:
            domain_obj = Domain.objects.get(name=domain)
        except Domain.DoesNotExist:
            return None
        return domain_obj.id

    @staticmethod
    def create_if_does_not_exist(domain: str):
        results = Domain.objects.filter(name=domain)
        if not results.exists():
            Domain.objects.create(name=domain, created_at=datetime.now())
        else:
            raise ValidationError("Domain already searched for previously")

    @staticmethod
    def update_last_refreshed(domain: str):
        domain_obj = Domain.objects.get(name=domain)
        domain_obj.created_at = datetime.now()
        domain_obj.save()

class PathModelService:
    @staticmethod
    def create_if_does_not_exist(path: str, domain_id: int):
        results = Path.objects.filter(path=path, domain__id=domain_id)
        if not results.exists():
            Path.objects.create(path=path, domain_id=domain_id)

class WebCrawlerService:
    domain: str
    created_at: datetime
    disallowed_paths: set[str]
    sitemap_urls: set[str]

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.get("domain")
        self.created_at = datetime.now()
        self.disallowed_paths = set()
        self.sitemap_urls = set()

    def _parse_robots_txt(self) -> None:
        url = f"https://{self.domain}/robots.txt"
        try:
            response = requests.get(url, timeout=5)
        except requests.RequestException as e:
            return None

        if response.status_code != 200:
            return None

        for line in response.text.splitlines():
            line = line.strip()
            if line.startswith("Disallow:"):
                path = line.split("Disallow:")[1].strip()
                if path:
                    self.disallowed_paths.add(path)
            if line.startswith("Sitemap:"):
                url = line.split("Sitemap:")[1].strip()
                if url:
                    self.sitemap_urls.add(url)

        return None

    def _parse_sitemaps_xml(self):
        domain_id = DomainModelService.get_domain_id_by_name(self.domain)

        for sitemap_url in self.sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=10)
                if response.status_code != 200:
                    continue
            except requests.RequestException:
                continue

            try:
                root = ElementTree.fromstring(response.content)
            except ElementTree.ParseError:
                continue

            for loc in root.findall(".//{*}loc"):
                url = loc.text.strip()
                parsed_url = urlparse(url)

                if parsed_url.netloc != self.domain:
                    continue

                path = parsed_url.path
                if not any(path.startswith(disallowed) for disallowed in self.disallowed_paths):
                    pass
                    PathModelService.create_if_does_not_exist(path=path, domain_id=domain_id)
        return None

    def _crawl_url(self) -> None:
        domain_id = DomainModelService.get_domain_id_by_name(self.domain)
        root_url = f"https://{self.domain}/"
        visited = set()
        queue = deque([root_url])

        while queue:
            current_url = queue.popleft()

            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                response = requests.get(current_url, timeout=10)
                if response.status_code != 200:
                    continue
            except requests.RequestException:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            links_found = set()

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                joined_url = urljoin(current_url, href)
                parsed = urlparse(joined_url)

                if parsed.netloc != self.domain:
                    continue

                path = parsed.path

                if any(path.startswith(disallowed) for disallowed in self.disallowed_paths):
                    continue

                links_found.add(joined_url)

                if joined_url not in visited:
                    queue.append(joined_url)

                PathModelService.create_if_does_not_exist(path, domain_id)

    def run(self):
        self._parse_robots_txt()
        self._parse_sitemaps_xml()
        self._crawl_url()

