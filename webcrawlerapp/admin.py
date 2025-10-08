from django.contrib import admin

from webcrawlerapp.models import Domain, Path

admin.site.register(Domain)
admin.site.register(Path)