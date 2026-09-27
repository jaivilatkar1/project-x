from django.urls import path

from assistantService.views.assistant_views import chat, history, sessions

urlpatterns = [
    path("chat", chat),
    path("history", history),
    path("sessions", sessions),
]
