from unicodedata import normalize

from django import forms

from .models import Idea, Script, Tag


class TaggedForm(forms.ModelForm):
    subjects = forms.CharField(
        label="Assuntos", required=False, max_length=500,
        help_text="Separe os assuntos com vírgulas. Para remover um assunto, apague seu nome.",
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Vesh, entrevistas"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["subjects"] = ", ".join(self.instance.tags.values_list("name", flat=True))

    def clean_subjects(self):
        names = {}
        for value in self.cleaned_data["subjects"].split(","):
            name = normalize("NFKC", " ".join(value.split()))
            if len(name) > 44:
                raise forms.ValidationError("Use até 44 caracteres por assunto.")
            if name:
                names.setdefault(name.casefold(), name)
        if len(names) > 12:
            raise forms.ValidationError("Adicione até 12 assuntos.")
        return names

    def apply_tags(self, instance):
        tags = [
            Tag.objects.get_or_create(key=key, defaults={"name": name})[0]
            for key, name in self.cleaned_data["subjects"].items()
        ]
        instance.tags.set(tags)


class IdeaForm(TaggedForm):
    class Meta:
        model = Idea
        fields = ("title", "note", "subjects")
        widgets = {"note": forms.Textarea(attrs={"rows": 5})}


class ConvertForm(forms.Form):
    format = forms.ChoiceField(label="Formato", choices=Script.Format.choices)


class ScriptForm(TaggedForm):
    class Meta:
        model = Script
        fields = ("title", "format", "subjects", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 15, "spellcheck": "true"})}
        help_texts = {"body": "Use # para títulos, **texto** para negrito e - para marcadores."}
