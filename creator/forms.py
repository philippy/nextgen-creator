from django import forms

from .models import Task, WeekFocus, WorkspaceSettings


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("title", "date", "time", "minutes", "script", "objective", "instructions", "learning")
        widgets = {
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "objective": forms.Textarea(attrs={"rows": 2}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
            "learning": forms.Textarea(attrs={"rows": 3}),
        }


class RescheduleForm(TaskForm):
    class Meta(TaskForm.Meta):
        fields = ("date", "time")


class FocusForm(forms.ModelForm):
    class Meta:
        model = WeekFocus
        fields = ("text", "script")
        help_texts = {"text": "Escreva uma prioridade ou escolha um roteiro. Deixe ambos em branco para limpar."}


class SettingsForm(forms.ModelForm):
    class Meta:
        model = WorkspaceSettings
        fields = ("weekly_goal_minutes",)
        labels = {"weekly_goal_minutes": "Meta semanal em minutos"}
        help_texts = {"weekly_goal_minutes": "20 horas equivalem a 1.200 minutos."}


class GuideForm(forms.ModelForm):
    class Meta:
        model = WorkspaceSettings
        fields = (
            "channel_proposal", "channel_audience", "channel_themes", "channel_voice", "approval_checklist",
        )
        widgets = dict.fromkeys(fields, forms.Textarea(attrs={"rows": 3}))
