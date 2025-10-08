from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from webcrawlerapp.forms import DomainSearchForm
from webcrawlerapp.models import Domain, Path
from webcrawlerapp.service import DomainModelService
from webcrawlerapp.tasks import run_web_crawler

class HomeView(APIView):
    renderer_classes = [TemplateHTMLRenderer]

    @staticmethod
    def get(request: Request) -> Response:
        context = {
            "form": DomainSearchForm(),
            "list_domains_url": reverse("list_domains")
        }

        return Response(template_name="search_view.html", data=context)

    def post(self, request: Request) -> HttpResponse:
        form = DomainSearchForm(request.POST)

        if not form.is_valid():
            for e in form.errors.values():
                messages.error(request, e.as_text())
            return redirect(".", allowed_host=request.get_host())

        domain = form.get_base_domain()

        try:
            DomainModelService.create_if_does_not_exist(domain)
            run_web_crawler.delay(domain)
            messages.success(request, "Crawling: " + domain)
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(".", allowed_host=request.get_host())

class DomainListView(ListView):
    model = Domain
    template_name = "domain_list.html"
    context_object_name = "domains"
    paginate_by = 5

class PathListView(ListView):
    model = Path
    template_name = "path_list.html"
    context_object_name = "paths"
    paginate_by = 10

    def get_queryset(self):
        domain_name = self.request.GET.get("domain")
        domain_id = DomainModelService.get_domain_id_by_name(domain_name)
        return Path.objects.filter(domain_id=domain_id).order_by("path")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        domain_name = self.request.GET.get("domain")
        context["domain_name"] = domain_name
        return context

class RefreshDomainView(APIView):
    @staticmethod
    def post(request: Request) -> HttpResponse:
        domain = request.POST.get("domain")

        DomainModelService.update_last_refreshed(domain)
        run_web_crawler.delay(domain)

        messages.success(request, f"Refreshing paths for {domain}, check back later!")
        base_url = reverse("list_paths")
        query_string = urlencode({"domain": domain})
        url = f"{base_url}?{query_string}"
        return redirect(url, allowed_host=request.get_host())