from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap

from challengeleak.sitemaps import StaticViewSitemap


sitemaps = {"static": StaticViewSitemap}


def robots_txt(request):
    domain = request.get_host()
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: https://{domain}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")



urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),

    path("", include("core.urls")),
]
