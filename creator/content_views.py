from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .content_forms import ConvertForm, IdeaForm, ProductionForm, ScriptForm
from .forms import GuideForm
from .markdown import render_markdown
from .models import Idea, Script, Tag, WorkspaceSettings
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
def script_detail(request, pk):
    script = get_object_or_404(Script, pk=pk)
    if script.status == Script.Status.DRAFT:
        return script_editor(request, pk)
    return render(request, "creator/script_read.html", {
        "section": "scripts", "script": script, "content": render_markdown(script.body),
    })


@require_http_methods(["GET", "POST"])
def script_editor(request, pk=None):
    script = get_object_or_404(Script, pk=pk) if pk else None
    initial = {}
    template = request.GET.get("modelo")
    if not script and template in Script.Format.values:
        initial = {"format": template, "body": (MODELS_DIR / f"{template}.md").read_text(encoding="utf-8")}
    approved = bool(script and script.status == Script.Status.APPROVED)
    form_class = ProductionForm if approved else ScriptForm
    submitted = request.method == "POST"
    form = form_class(request.POST if submitted else None, request.FILES if submitted else None, instance=script, initial=initial)
    storage = script.thumbnail.storage if approved else None
    valid = submitted and form.is_valid()
    approve = submitted and request.POST.get("action") == "approve" and not approved
    if approve and not form.cleaned_data.get("body"):
        form.add_error("body", "Preencha o texto completo para aprovar o roteiro.")
        valid = False
    if approved and valid and not form.cleaned_data["body"]:
        form.add_error("body", "Um roteiro aprovado precisa de texto.")
        valid = False
    if valid:
        new_thumbnail = None
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                current = Script.objects.filter(pk=saved.pk).values("status", "thumbnail").first() if saved.pk else None
                expected_status = Script.Status.APPROVED if approved else Script.Status.DRAFT
                if current and current["status"] != expected_status:
                    messages.warning(request, "O status do roteiro mudou. Abra o editor para continuar.")
                    return redirect(saved)
                old_thumbnail = current["thumbnail"] if current else ""
                if approved and form.cleaned_data.get("thumbnail_file"):
                    uploaded = form.cleaned_data["thumbnail_file"]
                    saved.thumbnail.save(uploaded.name, uploaded, save=False)
                    new_thumbnail = saved.thumbnail.name
                elif approved and form.cleaned_data.get("remove_thumbnail"):
                    saved.thumbnail = ""
                if approve:
                    saved.status = Script.Status.APPROVED
                if saved.pk:
                    model_fields = ["title", "format", "body", "edited_at"]
                    if approved:
                        model_fields.extend(("video_title", "thumbnail_text"))
                        if new_thumbnail or form.cleaned_data.get("remove_thumbnail"):
                            model_fields.append("thumbnail")
                    if approve:
                        model_fields.append("status")
                    saved.save(update_fields=model_fields)
                else:
                    saved.save()
                form.apply_tags(saved)
                if old_thumbnail and (new_thumbnail or form.cleaned_data.get("remove_thumbnail")):
                    transaction.on_commit(lambda: storage.delete(old_thumbnail), robust=True)
        except Exception:
            if new_thumbnail:
                storage.delete(new_thumbnail)
            raise
        messages.success(request, "Roteiro aprovado." if approve else "Roteiro salvo.")
        return redirect(saved)
    return render(request, "creator/script_editor.html", {
        "section": "scripts", "script": script, "form": form, "approved": approved,
        "title": "Editar roteiro" if script else "Novo roteiro",
        "return_to": script.get_absolute_url() if approved else reverse("scripts"),
    })


@require_POST
def script_reopen(request, pk):
    script = get_object_or_404(Script, pk=pk)
    Script.objects.filter(pk=pk, status=Script.Status.APPROVED).update(
        status=Script.Status.DRAFT, edited_at=timezone.now(),
    )
    messages.success(request, "Roteiro voltou para rascunho.")
    return redirect(script)


@never_cache
@require_safe
def thumbnail(request, pk):
    script = get_object_or_404(Script, pk=pk)
    if not script.thumbnail:
        raise Http404
    try:
        image = script.thumbnail.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    content_type = "image/png" if script.thumbnail.name.endswith(".png") else "image/jpeg"
    response = FileResponse(image, content_type=content_type)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["GET", "POST"])
def guide(request):
    form = GuideForm(request.POST if request.method == "POST" else None, instance=WorkspaceSettings.current())
    if request.method == "POST" and form.is_valid():
        guide_data = form.save(commit=False)
        guide_data.save(update_fields=GuideForm.Meta.fields)
        messages.success(request, "Guia do canal atualizado.")
        return redirect("guide")
    return render(request, "creator/guide.html", {
        "section": "guide", "form": form, "formats": Script.Format.choices,
    })


@require_POST
def script_preview(request):
    return HttpResponse(render_markdown(request.POST.get("body", "")))


def script_models(request):
    return render(request, "creator/script_models.html", {
        "section": "models", "formats": Script.Format.choices,
    })
