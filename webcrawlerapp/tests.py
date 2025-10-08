import unittest
from unittest.mock import patch, MagicMock

import requests
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import datetime

from webcrawlerapp.models import Domain, Path
from webcrawlerapp.service import DomainModelService, PathModelService, WebCrawlerService

class TestDomainModelService(TestCase):
    def setUp(self):
        self.domain_name = "example.com"
        self.domain_obj = Domain.objects.create(name=self.domain_name, created_at=datetime.now())

    def test_get_domain_id_by_name_exists(self):
        domain_id = DomainModelService.get_domain_id_by_name(self.domain_name)
        self.assertEqual(domain_id, self.domain_obj.id)

    def test_create_if_does_not_exist_new_domain(self):
        new_domain = "newdomain.com"
        DomainModelService.create_if_does_not_exist(new_domain)
        self.assertTrue(Domain.objects.filter(name=new_domain).exists())

    def test_create_if_does_not_exist_existing_domain(self):
        with self.assertRaises(ValidationError) as context:
            DomainModelService.create_if_does_not_exist(self.domain_name)

        self.assertEqual(str(context.exception.message), "Domain already searched for previously")

    def test_update_last_refreshed(self):
        original_time = self.domain_obj.created_at

        DomainModelService.update_last_refreshed(self.domain_name)
        self.domain_obj.refresh_from_db()

        self.assertGreater(self.domain_obj.created_at, original_time)


class TestPathModelService(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(name="example.com", created_at=datetime.now())
        self.existing_path = "/existing"
        Path.objects.create(path=self.existing_path, domain=self.domain)

    def test_create_if_does_not_exist_new_path(self):
        new_path = "/new-path"
        PathModelService.create_if_does_not_exist(new_path, self.domain.id)
        self.assertTrue(Path.objects.filter(path=new_path, domain=self.domain).exists())

    def test_create_if_does_not_exist_existing_path(self):
        initial_count = Path.objects.filter(domain=self.domain).count()

        PathModelService.create_if_does_not_exist(self.existing_path, self.domain.id)
        final_count = Path.objects.filter(domain=self.domain).count()

        self.assertEqual(initial_count, final_count)


class TestWebCrawlerService(TestCase):
    def setUp(self):
        self.domain_name = "example.com"
        self.domain = Domain.objects.create(name=self.domain_name, created_at=datetime.now())
        self.crawler = WebCrawlerService(domain=self.domain_name)

    @patch('requests.get')
    def test_parse_robots_txt_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        User-agent: *
        Disallow: /admin/
        Disallow: /private/
        Sitemap: https://example.com/sitemap.xml
        Sitemap: https://example.com/sitemap-news.xml
        """
        mock_get.return_value = mock_response

        self.crawler._parse_robots_txt()

        self.assertIn("/admin/", self.crawler.disallowed_paths)
        self.assertIn("/private/", self.crawler.disallowed_paths)
        self.assertIn("https://example.com/sitemap.xml", self.crawler.sitemap_urls)
        self.assertIn("https://example.com/sitemap-news.xml", self.crawler.sitemap_urls)

    @patch('requests.get')
    def test_parse_robots_txt_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        self.crawler._parse_robots_txt()

        self.assertEqual(len(self.crawler.disallowed_paths), 0)
        self.assertEqual(len(self.crawler.sitemap_urls), 0)

    @patch('requests.get')
    def test_parse_robots_txt_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection failed")

        self.crawler._parse_robots_txt()

        self.assertEqual(len(self.crawler.disallowed_paths), 0)
        self.assertEqual(len(self.crawler.sitemap_urls), 0)

    @patch('requests.get')
    @patch('webcrawlerapp.service.ElementTree.fromstring')
    @patch('webcrawlerapp.service.PathModelService.create_if_does_not_exist')
    def test_parse_sitemaps_xml_success(self, mock_create_path, mock_et, mock_get):
        self.crawler.sitemap_urls = {"https://example.com/sitemap.xml"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<xml>sitemap content</xml>"
        mock_get.return_value = mock_response

        mock_root = MagicMock()
        mock_loc1 = MagicMock()
        mock_loc1.text = "https://example.com/page1"
        mock_loc2 = MagicMock()
        mock_loc2.text = "https://example.com/page2"
        mock_loc3 = MagicMock()
        mock_loc3.text = "https://otherdomain.com/page3"
        mock_root.findall.return_value = [mock_loc1, mock_loc2, mock_loc3]
        mock_et.return_value = mock_root

        self.crawler._parse_sitemaps_xml()

        expected_calls = [
            unittest.mock.call(path="/page1", domain_id=self.domain.id),
            unittest.mock.call(path="/page2", domain_id=self.domain.id)
        ]
        mock_create_path.assert_has_calls(expected_calls, any_order=True)

    @patch('requests.get')
    @patch('webcrawlerapp.service.PathModelService.create_if_does_not_exist')
    def test_parse_sitemaps_xml_with_disallowed_paths(self, mock_create_path, mock_get):
        self.crawler.sitemap_urls = {"https://example.com/sitemap.xml"}
        self.crawler.disallowed_paths = {"/admin/"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<?xml version="1.0" encoding="UTF-8"?><urlset><url><loc>https://example.com/admin/secret</loc></url><url><loc>https://example.com/public/page</loc></url></urlset>'
        mock_get.return_value = mock_response

        self.crawler._parse_sitemaps_xml()

        mock_create_path.assert_called_once_with(path="/public/page", domain_id=self.domain.id)

    @patch('requests.get')
    @patch('webcrawlerapp.service.BeautifulSoup')
    @patch('webcrawlerapp.service.PathModelService.create_if_does_not_exist')
    def test_crawl_url_success(self, mock_create_path, mock_bs, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><a href='/page1'>Page1</a><a href='/page2'>Page2</a></body></html>"
        mock_get.return_value = mock_response

        mock_soup = MagicMock()

        mock_a1 = MagicMock()
        mock_a1.__getitem__ = lambda self, key: '/page1' if key == 'href' else None
        mock_a1.get = lambda key, default=None: '/page1' if key == 'href' else default
        mock_a2 = MagicMock()
        mock_a2.__getitem__ = lambda self, key: '/page2' if key == 'href' else None
        mock_a2.get = lambda key, default=None: '/page2' if key == 'href' else default

        mock_soup.find_all.return_value = [mock_a1, mock_a2]
        mock_bs.return_value = mock_soup

        self.crawler._crawl_url()

        actual_paths_called = []
        for call in mock_create_path.call_args_list:
            actual_paths_called.append(call[0][0])

        self.assertIn("/page1", actual_paths_called)
        self.assertIn("/page2", actual_paths_called)

    @patch('requests.get')
    @patch('webcrawlerapp.service.PathModelService.create_if_does_not_exist')
    def test_crawl_url_respects_disallowed_paths(self, mock_create_path, mock_get):
        self.crawler.disallowed_paths = {"/private/"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><a href='/private/secret'>Secret</a><a href='/public/page'>Public</a></body></html>"
        mock_get.return_value = mock_response

        mock_soup = MagicMock()

        mock_a1 = MagicMock()
        mock_a1.__getitem__ = lambda self, key: '/private/secret' if key == 'href' else None
        mock_a1.get = lambda key, default=None: '/private/secret' if key == 'href' else default
        mock_a2 = MagicMock()
        mock_a2.__getitem__ = lambda self, key: '/public/page' if key == 'href' else None
        mock_a2.get = lambda key, default=None: '/public/page' if key == 'href' else default

        mock_soup.find_all.return_value = [mock_a1, mock_a2]

        with patch('webcrawlerapp.service.BeautifulSoup', return_value=mock_soup):
            self.crawler._crawl_url()

        mock_create_path.assert_called_with("/public/page", self.domain.id)

    @patch('requests.get')
    def test_crawl_url_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection failed")

        try:
            self.crawler._crawl_url()
        except Exception as e:
            self.fail(f"_crawl_url raised {type(e).__name__} unexpectedly!")