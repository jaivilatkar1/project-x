from django.urls import path

from . import views

urlpatterns = [
    path("", views.serve_demo_ui),
    path("<str:filename>", views.serve_demo_static),
]
