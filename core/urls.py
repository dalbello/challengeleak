from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/process/", views.process, name="process"),
    path("api/waitlist/", views.waitlist, name="waitlist"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]
