from django.urls import path

from . import content_views, views

urlpatterns = [
    path("ideias/", content_views.ideas, name="ideas"),
    path("ideias/nova/", content_views.idea_form, name="idea_create"),
    path("ideias/<int:pk>/editar/", content_views.idea_form, name="idea_edit"),
    path("ideias/<int:pk>/arquivar/", content_views.idea_archive, name="idea_archive"),
    path("ideias/<int:pk>/rascunho/", content_views.idea_convert, name="idea_convert"),
    path("roteiros/", content_views.scripts, name="scripts"),
    path("roteiros/novo/", content_views.script_editor, name="script_create"),
    path("roteiros/previa/", content_views.script_preview, name="script_preview"),
    path("roteiros/<int:pk>/", content_views.script_editor, name="script_detail"),
    path("modelos/", content_views.script_models, name="script_models"),
    path("", views.today, name="today"),
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/foco/<str:monday>/", views.edit_focus, name="focus_edit"),
    path("tarefas/nova/", views.task_form, name="task_create"),
    path("tarefas/<int:pk>/", views.task_detail, name="task_detail"),
    path("tarefas/<int:pk>/editar/", views.task_form, name="task_edit"),
    path("tarefas/<int:pk>/reagendar/", views.task_form, {"reschedule": True}, name="task_reschedule"),
    path("tarefas/<int:pk>/status/", views.task_status, name="task_status"),
    path("configuracoes/", views.preferences, name="preferences"),
]
