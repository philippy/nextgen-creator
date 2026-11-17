from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .content_forms import ConvertForm, IdeaForm, ScriptForm
from .markdown import render_markdown
from .models import Idea, Script, Tag
from .views import safe_return

MODELS_DIR = Path(__file__).with_name("script_models")


def ideas(request):
    archived = request.GET.get("estado") == "arquivadas"
    filtered = Idea.objects.filter(archived_at__isnull=not archived).select_related("script").prefetch_related("tags")
    tag = request.GET.get("assunto", "")
    if tag:
        filtered = filtered.filter(tags__key=tag)
    return render(request, "creator/ideas.html", {
        "section": "ideas", "ideas": filtered, "tags": Tag.objects.all(), "selected_tag": tag, "archived": archived,
    })


@require_http_methods(["GET", "POST"])
def idea_form(request, pk=None):
    idea = get_object_or_404(Idea, pk=pk) if pk else None
    target = safe_return(request, reverse("ideas"))
    form = IdeaForm(request.POST if request.method == "POST" else None, instance=idea)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            form.apply_tags(saved)
        messages.success(request, "Ideia atualizada." if pk else "Ideia criada.")
        return redirect(target)
    return render(request, "creator/form.html", {
        "section": "ideas", "title": "Editar ideia" if idea else "Nova ideia", "form": form, "return_to": target,
    })


@require_POST
def idea_archive(request, pk):
    idea = get_object_or_404(Idea, pk=pk)
    restore = request.POST.get("restore") == "1"
    Idea.objects.filter(pk=idea.pk).update(archived_at=None if restore else timezone.now())
    messages.success(request, "Ideia restaurada." if restore else "Ideia arquivada.")
    return redirect(safe_return(request, reverse("ideas")))


@require_http_methods(["GET", "POST"])
def idea_convert(request, pk):
    idea = get_object_or_404(Idea.objects.select_related("script"), pk=pk)
    if hasattr(idea, "script"):
        return redirect(idea.script)
    form = ConvertForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            script, created = Script.objects.get_or_create(idea=idea, defaults={
                "title": idea.title, "body": idea.note, "format": form.cleaned_data["format"],
            })
            if created:
                script.tags.set(idea.tags.all())
        if created:
            messages.success(request, "Rascunho criado a partir da ideia.")
        return redirect(script)
    return render(request, "creator/form.html", {
        "section": "ideas", "title": f"Criar rascunho de {idea.title}", "form": form,
        "return_to": reverse("ideas"), "button_label": "Criar rascunho",
    })


def scripts(request):
    status = Script.Status.APPROVED if request.GET.get("aba") == "aprovados" else Script.Status.DRAFT
    filtered = Script.objects.filter(status=status).prefetch_related("tags")
    title = request.GET.get("busca", "").strip()
    tag = request.GET.get("assunto", "")
    format_value = request.GET.get("formato", "")
    if title:
        filtered = filtered.filter(title__icontains=title)
    if tag:
        filtered = filtered.filter(tags__key=tag)
    if format_value:
        filtered = filtered.filter(format=format_value)
    return render(request, "creator/scripts.html", {
        "section": "scripts", "scripts": filtered, "tags": Tag.objects.all(), "formats": Script.Format.choices,
        "search": title, "selected_tag": tag, "selected_format": format_value,
        "approved": status == Script.Status.APPROVED, "has_filters": bool(title or tag or format_value),
    })


@require_http_methods(["GET", "POST"])
def script_editor(request, pk=None):
    script = get_object_or_404(Script, pk=pk) if pk else None
    initial = {}
    template = request.GET.get("modelo")
    if not script and template in Script.Format.values:
        initial = {"format": template, "body": (MODELS_DIR / f"{template}.md").read_text(encoding="utf-8")}
    form = ScriptForm(request.POST if request.method == "POST" else None, instance=script, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            form.apply_tags(saved)
        messages.success(request, "Roteiro salvo.")
        return redirect(saved)
    return render(request, "creator/script_editor.html", {
        "section": "scripts", "script": script, "form": form,
        "title": "Editar roteiro" if script else "Novo roteiro", "return_to": reverse("scripts"),
    })


@require_POST
def script_preview(request):
    return HttpResponse(render_markdown(request.POST.get("body", "")))


def script_models(request):
    return render(request, "creator/script_models.html", {
        "section": "models", "formats": Script.Format.choices,
    })
