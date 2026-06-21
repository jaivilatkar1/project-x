from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    path("customers", views.list_customers),
    path("policy", views.get_policy),
    path("chat", views.chat),
    path("voice/capabilities", views.voice_capabilities),
    path("voice/transcribe", views.voice_transcribe),
    path("voice/chat", views.voice_chat),
    path("voice/speak", views.voice_speak),
    path("voice/realtime-session", views.voice_realtime_session),
    path("voice/execute-tool", views.voice_execute_tool),
    path("logs", views.reasoning_logs),
    path("logs/<str:session_id>", views.reasoning_logs),
    path("logs/<str:session_id>/stream", views.reasoning_stream),
]
