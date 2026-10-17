from django.urls import path

from agent import views

urlpatterns = [
    path("", views.chat_page, name="chat"),
    path("api/session", views.api_session_new, name="api_session_new"),
    path("api/session/reset", views.api_session_reset, name="api_session_reset"),
    path("api/chat", views.api_chat, name="api_chat"),
    path("api/meta", views.api_meta, name="api_meta"),
]
