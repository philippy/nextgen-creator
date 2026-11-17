from django.urls import path

from . import views

urlpatterns = [
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
