from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Task(models.Model):
    title = models.CharField("Título", max_length=180)
    date = models.DateField("Data", db_index=True)
    time = models.TimeField("Horário", blank=True, null=True)
    minutes = models.PositiveSmallIntegerField(
        "Duração estimada em minutos",
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        default=60,
    )
    objective = models.TextField("Objetivo", blank=True)
    instructions = models.TextField("Instruções", blank=True)
    learning = models.TextField("Nota de aprendizado", blank=True)
    done = models.BooleanField(default=False)

    class Meta:
        ordering = ("date", "done", models.F("time").asc(nulls_last=True), "pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("task_detail", args=[self.pk])


class WeekFocus(models.Model):
    monday = models.DateField(unique=True)
    text = models.CharField("Prioridade da semana", max_length=220, blank=True)


class WorkspaceSettings(models.Model):
    weekly_goal_minutes = models.PositiveSmallIntegerField(
        default=1200, validators=[MinValueValidator(15), MaxValueValidator(10080)]
    )

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Tag(models.Model):
    name = models.CharField("Assunto", max_length=44)
    key = models.CharField(max_length=132, unique=True, editable=False)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Idea(models.Model):
    title = models.CharField("Título", max_length=180)
    note = models.TextField("Nota", blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class Script(models.Model):
    class Format(models.TextChoices):
        SHORT = "short", "Short"
        LONG = "long", "Vídeo longo"
        DOCUMENTARY = "documentary", "Documentário"
        INTERVIEW = "interview", "Entrevista"

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        APPROVED = "approved", "Aprovado"

    title = models.CharField("Título interno", max_length=180)
    format = models.CharField("Formato", max_length=16, choices=Format)
    body = models.TextField("Texto completo em Markdown", blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT, db_index=True)
    tags = models.ManyToManyField(Tag, blank=True)
    idea = models.OneToOneField(Idea, related_name="script", blank=True, null=True, on_delete=models.SET_NULL)
    edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-edited_at", "-pk")

    def get_absolute_url(self):
        return reverse("script_detail", args=[self.pk])

    def __str__(self):
        return self.title
