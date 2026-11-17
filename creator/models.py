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
