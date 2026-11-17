import hashlib
import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings
from django.urls import reverse

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"
SCOPES = (
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
)
CALENDAR_NAME = "Nextgen Creator"
TIME_ZONE = "America/Sao_Paulo"


class CalendarError(Exception):
    def __init__(self, status=None, code=None):
        super().__init__("O Google Calendar não respondeu como esperado.")
        self.status = status
        self.code = code


def is_configured():
    try:
        url = urlsplit(settings.NEXTGEN_PUBLIC_URL)
        local = settings.DEBUG and url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        valid_url = (
            (url.scheme == "https" or local) and url.hostname and
            not any((url.path, url.query, url.fragment, url.username, url.password))
        )
    except ValueError:
        return False
    return bool(valid_url and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def callback_url():
    return settings.NEXTGEN_PUBLIC_URL + reverse("google_callback")


def authorization_url(state):
    return AUTH_URL + "?" + urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": callback_url(), "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
    })


def request_json(url, *, method="GET", token=None, form=None, payload=None):
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        data = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, method=method, headers=headers, data=data), timeout=7) as response:
            result = json.load(response)
    except HTTPError as error:
        with error:
            try:
                info = json.load(error)
            except (ValueError, OSError):
                info = {}
        code = info.get("error") if isinstance(info, dict) else None
        raise CalendarError(error.code, code if isinstance(code, str) else None) from error
    except (URLError, OSError, ValueError) as error:
        raise CalendarError() from error
    if not isinstance(result, dict):
        raise CalendarError()
    return result


def token_request(**fields):
    result = request_json(TOKEN_URL, method="POST", form={
        "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET, **fields,
    })
    if not result.get("access_token"):
        raise CalendarError()
    return result


def connect(code, workspace):
    credentials = token_request(grant_type="authorization_code", code=code, redirect_uri=callback_url())
    refresh = credentials.get("refresh_token")
    granted = credentials.get("scope")
    if not refresh or (granted is not None and not set(SCOPES).issubset(granted.split())):
        raise CalendarError()
    calendar = find_or_create_calendar(credentials["access_token"], workspace.calendar_marker)
    return refresh, calendar


def find_or_create_calendar(token, marker):
    description = f"Calendário de tarefas do Nextgen Creator. Instalação {marker.hex}."
    query = {"minAccessRole": "owner", "showHidden": "true"}
    while True:
        result = request_json(f"{API}/users/me/calendarList?{urlencode(query)}", token=token)
        for calendar in result.get("items", []):
            if not calendar.get("primary") and calendar.get("description") == description and calendar.get("id"):
                return calendar["id"]
        page = result.get("nextPageToken")
        if not page:
            break
        query["pageToken"] = page

    calendar = request_json(f"{API}/calendars", method="POST", token=token, payload={
        "summary": CALENDAR_NAME, "description": description, "timeZone": TIME_ZONE,
    })
    if not calendar.get("id"):
        raise CalendarError()
    return calendar["id"]


def event_id(task_id, marker):
    return "ng" + hashlib.sha256(f"{marker.hex}:{task_id}".encode()).hexdigest()


def send_event(task, workspace):
    access = token_request(grant_type="refresh_token", refresh_token=workspace.google_refresh_token)["access_token"]
    endpoint = f"{API}/calendars/{quote(task.google_calendar_id, safe='')}/events"
    identifier = event_id(task.pk, workspace.calendar_marker)
    start = datetime.combine(task.date, task.time, tzinfo=ZoneInfo(TIME_ZONE))
    finish = start + timedelta(minutes=task.minutes)
    task_url = settings.NEXTGEN_PUBLIC_URL + task.get_absolute_url()
    event = {
        "id": identifier,
        "summary": task.title,
        "description": f"Tarefa no Nextgen Creator: {task_url}",
        "start": {"dateTime": start.isoformat(), "timeZone": TIME_ZONE},
        "end": {"dateTime": finish.isoformat(), "timeZone": TIME_ZONE},
    }

    try:
        created = request_json(endpoint, method="POST", token=access, payload=event)
    except CalendarError as error:
        if error.status != 409:
            raise
        created = request_json(f"{endpoint}/{identifier}", token=access)
    link = created.get("htmlLink")
    if not link or len(link) > 2048:
        raise CalendarError()
    try:
        url = urlsplit(link)
    except ValueError as error:
        raise CalendarError() from error
    if url.scheme != "https" or url.netloc not in {"calendar.google.com", "www.google.com", "google.com"}:
        raise CalendarError()
    return link
