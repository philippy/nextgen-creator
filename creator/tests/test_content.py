from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from creator.models import Idea, Script, Tag


class ContentFlowTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("phil"))

    def test_capture_return_and_idempotent_conversion(self):
        response = self.client.post(reverse("idea_create"), {
            "title": "Entrevista com Vesh", "note": "## Pensar por si", "subjects": "Vesh, Consciência, vesh",
            "next": reverse("agenda"),
        })
        self.assertRedirects(response, reverse("agenda"))
        idea = Idea.objects.get()
        convert = reverse("idea_convert", args=[idea.pk])
        for _ in range(2):
            self.client.post(convert, {"format": Script.Format.INTERVIEW})
        script = Script.objects.get(idea=idea)
        self.assertEqual(script.body, idea.note)
        self.assertCountEqual(script.tags.values_list("name", flat=True), ["Vesh", "Consciência"])
        self.assertContains(self.client.get(script.get_absolute_url()), "## Pensar por si")
        filtered = self.client.get(reverse("scripts"), {
            "assunto": "vesh", "formato": Script.Format.INTERVIEW, "busca": "Vesh",
        })
        self.assertContains(filtered, script.title)
        self.assertContains(self.client.get(reverse("ideas"), {"assunto": "vesh"}), script.get_absolute_url())
        self.assertContains(self.client.get(reverse("ideas"), {"assunto": "sem-resultados"}), "Limpar filtros")

    def test_shared_tags_can_be_removed_from_script(self):
        idea = Idea.objects.create(title="Ideia")
        tag = Tag.objects.create(name="Vesh", key="vesh")
        idea.tags.add(tag)
        self.client.post(reverse("idea_convert", args=[idea.pk]), {"format": "long"})
        script = Script.objects.get(idea=idea)
        self.client.post(script.get_absolute_url(), {"title": "Roteiro", "format": "short", "subjects": "Outras ideias"})
        self.assertEqual(script.tags.get().name, "Outras ideias")
        self.assertEqual(idea.tags.get(), tag)

    def test_ideas_archive_and_restore(self):
        idea = Idea.objects.create(title="Ideia arquivável")
        route = reverse("idea_archive", args=[idea.pk])
        self.client.post(route, {"restore": "0"})
        self.assertNotContains(self.client.get(reverse("ideas")), idea.title)
        self.assertContains(self.client.get(reverse("ideas"), {"estado": "arquivadas"}), idea.title)
        self.client.post(route, {"restore": "1"})
        self.assertContains(self.client.get(reverse("ideas")), idea.title)

    def test_models_and_safe_preview(self):
        for format_value, heading in [
            ("short", "Gancho"), ("long", "Promessa"),
            ("documentary", "Pergunta central"), ("interview", "Contexto"),
        ]:
            self.assertContains(self.client.get(reverse("script_create"), {"modelo": format_value}), heading)
        response = self.client.post(reverse("script_preview"), {
            "body": "# Título\n\n- **Destaque**\n\n<img src=x onerror=alert(1)>"
        })
        self.assertContains(response, "<h2>Título</h2><ul><li><strong>Destaque</strong></li></ul>")
        self.assertContains(response, "&lt;img")
        self.assertNotContains(response, "<img")
