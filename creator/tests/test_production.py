from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from creator.models import Idea, Script, Task


def sample_image():
    output = BytesIO()
    Image.new("RGB", (20, 10), "lightblue").save(output, "PNG")
    return SimpleUploadedFile("thumb.png", output.getvalue(), content_type="image/png")


class ProductionFlowTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("phil"))
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.enterContext(self.settings(MEDIA_ROOT=temporary.name))
        self.idea = Idea.objects.create(title="Entrevista com Vesh")
        self.script = Script.objects.create(title=self.idea.title, format="interview", idea=self.idea)
        self.edit = reverse("script_edit", args=[self.script.pk])
        self.thumb = reverse("thumbnail", args=[self.script.pk])
        self.fields = {"title": self.idea.title, "format": "interview", "subjects": "Vesh"}

    def approve(self):
        self.client.post(self.script.get_absolute_url(), {**self.fields, "body": "## Pensar por si", "action": "approve"})
        self.script.refresh_from_db()

    def test_approve_thumb_schedule_and_reopen(self):
        canonical = self.script.get_absolute_url()
        response = self.client.post(canonical, {**self.fields, "body": " ", "action": "approve"})
        self.assertContains(response, "Preencha o texto completo")
        self.approve()
        self.assertEqual(self.script.status, Script.Status.APPROVED)
        self.assertContains(self.client.get(reverse("scripts"), {"aba": "aprovados", "assunto": "vesh"}), self.script.title)
        self.assertContains(self.client.get(canonical), "<h3>Pensar por si</h3>")
        self.client.post(self.edit, {**self.fields, "body": "## Pensar por si", "thumbnail_file": sample_image()})
        image = self.client.get(self.thumb)
        self.assertEqual(image.headers["Content-Type"], "image/png")
        self.assertIn("private", image.headers["Cache-Control"])
        self.assertTrue(b"".join(image.streaming_content).startswith(b"\x89PNG"))

        create = f"{reverse('task_create')}?roteiro={self.script.pk}"
        self.assertEqual(self.client.get(create).context["form"].initial["script"], self.script.pk)
        self.client.post(create, {"title": "Gravar Vesh", "date": timezone.localdate(), "minutes": 60, "script": self.script.pk})
        task = Task.objects.get()
        self.assertContains(self.client.get(reverse("today")), task.title)
        self.assertContains(self.client.get(task.get_absolute_url()), canonical)
        self.client.post(reverse("script_reopen", args=[self.script.pk]))
        self.script.refresh_from_db()
        self.assertEqual(self.script.status, Script.Status.DRAFT)
        self.assertEqual(self.script.idea, self.idea)
        self.assertEqual(task.script_id, self.script.pk)
        self.assertEqual(self.script.get_absolute_url(), canonical)

        self.client.logout()
        self.assertEqual(self.client.get(self.thumb).status_code, 302)
        self.assertEqual(self.client.get("/media/thumb.png").status_code, 404)

    def test_reject_invalid_thumbnail_and_remove_valid_image(self):
        self.approve()
        payload = {**self.fields, "body": "Roteiro completo"}
        fake = SimpleUploadedFile("falso.jpg", b"<script>test</script>", content_type="image/jpeg")
        self.assertContains(self.client.post(self.edit, {**payload, "thumbnail_file": fake}), "Envie um arquivo JPG ou PNG")
        self.client.post(self.edit, {**payload, "thumbnail_file": sample_image()})
        self.script.refresh_from_db()
        first = self.script.thumbnail.name
        storage = self.script.thumbnail.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.edit, {**payload, "thumbnail_file": sample_image()})
        self.assertFalse(storage.exists(first))
        self.script.refresh_from_db()
        second = self.script.thumbnail.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.edit, {**payload, "remove_thumbnail": "on"})
        self.assertEqual(self.client.get(self.thumb).status_code, 404)
        self.assertFalse(storage.exists(second))

    def test_guide_and_linked_weekly_focus(self):
        route = reverse("guide")
        self.client.post(route, {"channel_proposal": "Questionar o que aprendemos"})
        self.assertContains(self.client.get(route), "Questionar o que aprendemos")
        self.assertContains(self.client.get(route), "Usar modelo Entrevista")
        route = reverse("focus_edit", args=[timezone.localdate().isoformat()])
        self.client.post(route, {"script": self.script.pk})
        self.assertContains(self.client.get(reverse("today")), "Abrir roteiro")
