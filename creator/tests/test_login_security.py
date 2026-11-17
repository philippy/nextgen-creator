from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from axes.models import AccessAttempt

from creator.security import get_client_ip


@override_settings(AXES_ENABLED=True)
class LoginSecurityTests(TestCase):
    def setUp(self):
        self.phil = get_user_model().objects.create_user("phil", password="phil-test-password")
        self.other = get_user_model().objects.create_user("second", password="second-test-password")
        self.login_url = reverse("login")

    def test_only_phil_can_authenticate(self):
        response = self.client.post(
            self.login_url,
            {"username": "second", "password": "second-test-password"},
            REMOTE_ADDR="198.51.100.21",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_previously_authenticated_non_phil_session_is_rejected(self):
        self.client.force_login(self.other, backend="django.contrib.auth.backends.ModelBackend")

        response = self.client.get(reverse("today"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/entrar/?next=/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_fifth_failed_attempt_returns_429_lockout(self):
        for attempt in range(4):
            response = self.client.post(
                self.login_url,
                {"username": "phil", "password": f"wrong-{attempt}"},
                REMOTE_ADDR="198.51.100.31",
            )
            self.assertNotEqual(response.status_code, 429)

        locked = self.client.post(
            self.login_url,
            {"username": "phil", "password": "wrong-fifth"},
            REMOTE_ADDR="198.51.100.31",
        )

        self.assertEqual(locked.status_code, 429)
        self.assertTrue(AccessAttempt.objects.filter(ip_address="198.51.100.31").exists())

    def test_lockout_is_scoped_to_client_ip(self):
        for attempt in range(5):
            self.client.post(
                self.login_url,
                {"username": "phil", "password": f"wrong-{attempt}"},
                REMOTE_ADDR="198.51.100.41",
            )

        response = self.client.post(
            self.login_url,
            {"username": "phil", "password": "phil-test-password"},
            REMOTE_ADDR="198.51.100.42",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.phil.pk))

    def test_client_spoofed_forwarded_for_does_not_override_remote_addr(self):
        first = self._request("198.51.100.51", "203.0.113.99")
        second = self._request("198.51.100.52", "203.0.113.99")

        self.assertEqual(get_client_ip(first), "198.51.100.51")
        self.assertEqual(get_client_ip(second), "198.51.100.52")

    def test_loopback_proxy_forwarded_ip_is_used(self):
        request = self._request("127.0.0.1", "198.51.100.61")

        self.assertEqual(get_client_ip(request), "198.51.100.61")

    @staticmethod
    def _request(remote_addr, forwarded_for):
        from django.test import RequestFactory

        return RequestFactory().post(
            "/entrar/",
            REMOTE_ADDR=remote_addr,
            HTTP_X_FORWARDED_FOR=forwarded_for,
        )
