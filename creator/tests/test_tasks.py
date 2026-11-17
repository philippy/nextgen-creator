from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from creator.models import Task


class TaskFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("phil", password="local-test-password")
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def create(self, **changes):
        values = {"title": "Gravar entrevista", "date": self.today, "time": "10:30", "minutes": 90}
        values.update(changes)
        return self.client.post(reverse("task_create"), values)

    def test_login_and_persistence(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("today")), "/entrar/?next=/")
        self.assertRedirects(
            self.client.post(reverse("login"), {"username": "phil", "password": "local-test-password"}),
            reverse("today"),
        )
        self.assertEqual(self.create().status_code, 302)
        task = Task.objects.get()
        self.assertEqual(task.date, self.today)
        self.assertContains(self.client.get(reverse("today")), task.title)

    def test_conclude_undo_and_move_to_another_week(self):
        self.create()
        task = Task.objects.get()
        status = reverse("task_status", args=[task.pk])
        for done, completed in [("1", 90), ("0", 0)]:
            self.client.post(status, {"done": done})
            self.assertEqual(self.client.get(reverse("agenda")).context["completed"], completed)
        new_date = self.today + timedelta(days=7)
        self.client.post(reverse("task_reschedule", args=[task.pk]), {"date": new_date})
        self.assertEqual(self.client.get(reverse("agenda")).context["planned"], 0)
        new_week = self.client.get(reverse("agenda"), {"semana": new_date})
        self.assertEqual(new_week.context["planned"], 90)
        self.assertContains(new_week, task.title)

    def test_capacity_over_goal_and_validation(self):
        self.create(minutes=1320)
        response = self.client.get(reverse("today"))
        self.assertEqual(response.context["excess"], 120)
        self.assertContains(response, "Acima da meta")
        response = self.create(title="Título mantido", minutes=0)
        self.assertContains(response, "Título mantido")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertEqual(Task.objects.count(), 1)

    def test_today_order_and_overdue(self):
        self.create(title="Sem horário", time="")
        self.create(title="Primeira", time="08:00")
        self.create(title="Feita", time="07:00")
        self.create(title="Atrasada", date=self.today - timedelta(days=1))
        self.client.post(reverse("task_status", args=[Task.objects.get(title="Feita").pk]), {"done": "1"})
        response = self.client.get(reverse("today"))
        self.assertEqual([task.title for task in response.context["tasks"]], ["Primeira", "Sem horário", "Feita"])
        self.assertEqual([task.title for task in response.context["overdue"]], ["Atrasada"])

    def test_weekly_focus(self):
        route = reverse("focus_edit", args=[self.today.isoformat()])
        self.client.post(route, {"text": "Treinar a abertura de vídeo"})
        self.assertContains(self.client.get(reverse("today")), "Treinar a abertura de vídeo")
