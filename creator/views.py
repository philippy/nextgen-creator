from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from . import google_calendar
from .forms import FocusForm, RescheduleForm, SettingsForm, TaskForm
from .models import Script, Task, WeekFocus, WorkspaceSettings


def selected_date(value, default):
    try:
        parsed = date.fromisoformat(value) if value else default
        return parsed if 1900 <= parsed.year <= 9998 else default
    except ValueError:
        return default


def monday_of(day):
    return day - timedelta(days=day.weekday())


def week_url(monday):
    return f"{reverse('agenda')}?semana={monday.isoformat()}"


def safe_return(request, fallback):
    target = request.POST.get("next") if request.method == "POST" else request.GET.get("next")
    if target and target.startswith("/") and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def week_context(monday):
    sunday = monday + timedelta(days=6)
    tasks = list(Task.objects.filter(date__range=(monday, sunday)).select_related("script"))
    goal = WorkspaceSettings.current().weekly_goal_minutes
    planned = sum(task.minutes for task in tasks)
    return {
        "monday": monday,
        "sunday": sunday,
        "week_tasks": tasks,
        "focus": WeekFocus.objects.filter(monday=monday).select_related("script").first(),
        "goal": goal,
        "planned": planned,
        "completed": sum(task.minutes for task in tasks if task.done),
        "remaining": max(goal - planned, 0),
        "excess": max(planned - goal, 0),
        "progress": min(round(planned * 100 / goal), 100),
    }


def today(request):
    day = timezone.localdate()
    context = week_context(monday_of(day))
    context.update({
        "section": "today",
        "day": day,
        "tasks": [task for task in context["week_tasks"] if task.date == day],
        "overdue": Task.objects.filter(date__lt=day, done=False).select_related("script"),
    })
    return render(request, "creator/today.html", context)


def agenda(request):
    current_day = timezone.localdate()
    monday = monday_of(selected_date(request.GET.get("semana"), current_day))
    context = week_context(monday)
    context.update({
        "section": "agenda",
        "current_day": current_day,
        "previous": week_url(monday - timedelta(days=7)),
        "following": week_url(monday + timedelta(days=7)),
        "days": [],
    })
    for offset in range(7):
        day = monday + timedelta(days=offset)
        tasks = [task for task in context["week_tasks"] if task.date == day]
        context["days"].append({"date": day, "tasks": tasks, "total": sum(task.minutes for task in tasks)})
    return render(request, "creator/agenda.html", context)


@require_http_methods(["GET", "POST"])
def edit_focus(request, monday):
    week = monday_of(selected_date(monday, timezone.localdate()))
    focus = WeekFocus.objects.filter(monday=week).first()
    if focus is None:
        focus = WeekFocus(monday=week)
    target = safe_return(request, week_url(week))
    form = FocusForm(request.POST if request.method == "POST" else None, instance=focus)
    if request.method == "POST" and form.is_valid():
        WeekFocus.objects.update_or_create(monday=week, defaults=form.cleaned_data)
        messages.success(request, "Prioridade da semana salva.")
        return redirect(target)
    return render(request, "creator/form.html", {
        "section": "agenda", "title": "Prioridade da semana", "form": form, "return_to": target,
    })


def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("script"), pk=pk)
    workspace = WorkspaceSettings.current()
    return render(request, "creator/task_detail.html", {
        "section": "agenda", "task": task, "return_to": safe_return(request, week_url(monday_of(task.date))),
        "google_connected": bool(google_calendar.is_configured() and workspace.google_refresh_token and workspace.google_calendar_id),
    })


@require_http_methods(["GET", "POST"])
def task_form(request, pk=None, reschedule=False):
    task = get_object_or_404(Task, pk=pk) if pk else None
    initial = {"date": selected_date(request.GET.get("data"), timezone.localdate())}
    script_id = request.GET.get("roteiro", "")
    if not task and script_id.isascii() and script_id.isdecimal() and len(script_id) <= 18:
        script = Script.objects.filter(pk=request.GET["roteiro"], status=Script.Status.APPROVED).first()
        if script:
            initial.update(script=script.pk, title=f"Gravar: {script.title}"[:180])
    form_class = RescheduleForm if reschedule else TaskForm
    form = form_class(request.POST if request.method == "POST" else None, instance=task, initial=initial if not task else None)
    target = safe_return(request, task.get_absolute_url() if task else week_url(monday_of(initial["date"])))
    if request.method == "POST" and form.is_valid():
        if reschedule:
            Task.objects.filter(pk=task.pk).update(**form.cleaned_data)
            messages.success(request, "Tarefa reagendada.")
        else:
            task = form.save(commit=False)
            task.save(update_fields=TaskForm.Meta.fields if pk else None)
            messages.success(request, "Tarefa atualizada." if pk else "Tarefa criada.")
        return redirect(safe_return(request, task.get_absolute_url()))
    title = "Reagendar tarefa" if reschedule else ("Editar tarefa" if task else "Nova tarefa")
    return render(request, "creator/form.html", {
        "section": "agenda", "title": title, "form": form, "return_to": target,
    })


@require_POST
def task_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    state = request.POST.get("done")
    if state not in {"0", "1"}:
        messages.error(request, "Não foi possível atualizar o estado da tarefa.")
        return redirect(safe_return(request, task.get_absolute_url()))
    done = state == "1"
    Task.objects.filter(pk=pk).update(done=done)
    messages.success(request, "Tarefa concluída." if done else "Tarefa reaberta.")
    return redirect(safe_return(request, task.get_absolute_url()))


@require_http_methods(["GET", "POST"])
def preferences(request):
    workspace = WorkspaceSettings.current()
    form = SettingsForm(request.POST if request.method == "POST" else None, instance=workspace)
    if request.method == "POST" and form.is_valid():
        form.save(commit=False).save(update_fields=SettingsForm.Meta.fields)
        messages.success(request, "Configurações salvas.")
        return redirect("preferences")
    return render(request, "creator/preferences.html", {
        "section": "preferences", "form": form,
        "google_configured": google_calendar.is_configured(),
        "google_connected": bool(workspace.google_refresh_token and workspace.google_calendar_id),
    })
