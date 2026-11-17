from secrets import compare_digest, token_urlsafe
from time import time

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_safe

from . import google_calendar as google
from .models import Task, WorkspaceSettings

OAUTH_SESSION_KEY = "nextgen_google_oauth"


@require_POST
def start(request):
    if not google.is_configured():
        messages.error(request, "Configure as credenciais e a URL do Google Calendar no servidor.")
        return redirect("preferences")
    state = token_urlsafe(32)
    request.session[OAUTH_SESSION_KEY] = {"state": state, "created": int(time())}
    return redirect(google.authorization_url(state))


@require_safe
def callback(request):
    attempt = request.session.get(OAUTH_SESSION_KEY)
    received = request.GET.get("state", "")
    if (not attempt or time() - attempt["created"] > 600 or
            not received.isascii() or not compare_digest(received, attempt["state"])):
        messages.error(request, "A tentativa de conexão expirou ou é inválida. Inicie a conexão novamente.")
        return redirect("preferences")
    request.session.pop(OAUTH_SESSION_KEY, None)
    code = request.GET.get("code")
    if not code or not google.is_configured():
        messages.error(request, "A autorização do Google não foi concluída. Você pode tentar novamente.")
        return redirect("preferences")
    workspace = WorkspaceSettings.current()
    try:
        refresh, calendar_id = google.connect(code, workspace)
    except google.CalendarError:
        messages.error(request, "Não foi possível conectar a agenda. Confira as permissões e tente novamente.")
        return redirect("preferences")
    WorkspaceSettings.objects.filter(pk=workspace.pk).update(
        google_refresh_token=refresh, google_calendar_id=calendar_id,
    )
    messages.success(request, "Google Calendar conectado à agenda Nextgen Creator.")
    return redirect("preferences")


@require_POST
def disconnect(request):
    WorkspaceSettings.objects.filter(pk=1).update(google_refresh_token="", google_calendar_id="")
    request.session.pop(OAUTH_SESSION_KEY, None)
    messages.success(request, "Google Calendar desconectado.")
    return redirect("preferences")


@require_POST
def send(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.google_event_url:
        messages.info(request, "A tarefa já está no Google Calendar.")
        return redirect(task)
    if not task.time:
        messages.error(request, "Defina um horário antes de enviar a tarefa ao Google Calendar.")
        return redirect(task)

    workspace = WorkspaceSettings.current()
    if not (google.is_configured() and workspace.google_refresh_token and workspace.google_calendar_id):
        messages.error(request, "Conecte o Google Calendar em Configurações antes de enviar.")
        return redirect(task)

    with transaction.atomic():
        task.refresh_from_db()
        if task.google_event_url:
            messages.info(request, "A tarefa já está no Google Calendar.")
            return redirect(task)
        if not task.time:
            messages.error(request, "Defina um horário antes de enviar a tarefa ao Google Calendar.")
            return redirect(task)
        if task.google_calendar_id and task.google_calendar_id != workspace.google_calendar_id:
            messages.error(request, "Reconecte a conta Google usada na primeira tentativa para reenviar esta tarefa.")
            return redirect(task)
        if not task.google_calendar_id:
            task.google_calendar_id = workspace.google_calendar_id
            task.save(update_fields=["google_calendar_id"])

    try:
        event_url = google.send_event(task, workspace)
    except google.CalendarError as error:
        Task.objects.filter(pk=pk, google_event_url="").update(google_send_failed=True)
        if error.code == "invalid_grant":
            WorkspaceSettings.objects.filter(pk=workspace.pk, google_refresh_token=workspace.google_refresh_token).update(
                google_refresh_token="",
            )
            messages.error(request, "A conexão com o Google expirou. Reconecte em Configurações e tente novamente.")
        else:
            messages.error(request, "Falha ao enviar ao Google Calendar. A tarefa foi mantida. Tente novamente.")
    else:
        Task.objects.filter(pk=pk).update(google_event_url=event_url, google_send_failed=False)
        messages.success(request, "Tarefa adicionada ao Google Calendar.")
    return redirect(task)
