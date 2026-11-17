from datetime import date, time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from creator import google_calendar as google
from creator.models import Task, WorkspaceSettings

EVENT_LINK = "https://calendar.google.com/calendar/event?eid=vesh"


@override_settings(
    GOOGLE_CLIENT_ID="test-app", GOOGLE_CLIENT_SECRET="test-secret", NEXTGEN_PUBLIC_URL="https://creator.example.test",
)
class CalendarTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("phil"))
        self.workspace = WorkspaceSettings.current()
        self.task = Task.objects.create(
            title="Gravar com Vesh", date=date(2026, 11, 17), time=time(23, 30), minutes=90,
        )

    def test_oauth_state_single_use_and_recognizes_its_secondary_calendar(self):
        route = reverse("google_start")
        location = self.client.post(route).headers["Location"]
        params = parse_qs(urlsplit(location).query)
        self.assertEqual(params["redirect_uri"], ["https://creator.example.test/configuracoes/google/retorno/"])
        self.assertEqual(params["access_type"], ["offline"])
        state = params["state"][0]
        callback = reverse("google_callback")

        calendar_description = f"Calendário de tarefas do Nextgen Creator. Instalação {self.workspace.calendar_marker.hex}."
        with patch("creator.google_calendar.request_json", side_effect=[
            {"access_token": "access", "refresh_token": "refresh", "scope": " ".join(google.SCOPES)},
            {"items": [], "nextPageToken": "page"},
            {"items": [{"description": calendar_description, "id": "secondary@group.calendar.google.com"}]},
        ]) as request_json:
            self.client.get(callback, {"state": "erro", "code": "code"})
            request_json.assert_not_called()
            self.client.get(callback, {"state": state, "code": "code"})
            self.assertEqual(request_json.call_count, 3)
            self.client.get(callback, {"state": state, "code": "code"})
            self.assertEqual(request_json.call_count, 3)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.google_refresh_token, "refresh")
        self.assertEqual(self.workspace.google_calendar_id, "secondary@group.calendar.google.com")

    def test_calendar_creation_and_deduplication_after_lost_response(self):
        def service(url, **kwargs):
            if url == google.TOKEN_URL:
                return {"access_token": "access"}
            if kwargs.get("method") == "POST":
                body = kwargs["payload"]
                attempts.append(body)
                if body["id"] in remote_events:
                    raise google.CalendarError(409)
                remote_events[body["id"]] = body
                raise google.CalendarError()
            self.assertIn(url.split("/")[-1], remote_events)
            return {"htmlLink": EVENT_LINK}

        self.workspace.google_refresh_token = "refresh"
        with patch("creator.google_calendar.request_json", side_effect=[{"items": []}, {"id": "secondary"}]) as api:
            self.workspace.google_calendar_id = google.find_or_create_calendar("access", self.workspace.calendar_marker)
            self.assertEqual(api.call_args.kwargs["payload"]["summary"], "Nextgen Creator")
        self.workspace.save(update_fields=["google_refresh_token", "google_calendar_id"])

        attempts = []
        remote_events = {}
        send = reverse("google_send", args=[self.task.pk])
        with patch("creator.google_calendar.request_json", side_effect=service) as api:
            response = self.client.post(send, follow=True)
            self.assertContains(response, "Tentar novamente")
            self.assertContains(response, self.task.title)
            response = self.client.post(send, follow=True)
            self.assertContains(response, "Abrir no Google Calendar")
            self.assertContains(response, EVENT_LINK)
            count = api.call_count
            self.client.post(send)
            self.assertEqual(api.call_count, count)

        self.assertEqual(len(remote_events), 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], attempts[1])
        self.assertEqual(attempts[0]["start"], {"dateTime": "2026-11-17T23:30:00-03:00", "timeZone": "America/Sao_Paulo"})
        self.assertEqual(attempts[0]["end"], {"dateTime": "2026-11-18T01:00:00-03:00", "timeZone": "America/Sao_Paulo"})
        self.assertIn("https://creator.example.test" + self.task.get_absolute_url(), attempts[0]["description"])
        self.task.refresh_from_db()
        self.assertFalse(self.task.google_send_failed)
        self.assertEqual(self.task.google_event_url, EVENT_LINK)

    def test_no_time_and_pending_send_cannot_move_across_calendars(self):
        self.workspace.google_calendar_id = "nova-agenda"
        self.workspace.google_refresh_token = "refresh"
        self.workspace.save(update_fields=["google_calendar_id", "google_refresh_token"])
        send = reverse("google_send", args=[self.task.pk])
        with patch("creator.google_calendar.send_event") as request:
            Task.objects.filter(pk=self.task.pk).update(time=None)
            self.assertContains(self.client.post(send, follow=True), "Defina um horário")
            Task.objects.filter(pk=self.task.pk).update(time=time(10), google_calendar_id="agenda-original")
            self.assertContains(self.client.post(send, follow=True), "Reconecte a conta Google")
            request.assert_not_called()
