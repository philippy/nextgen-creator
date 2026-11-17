from io import BytesIO
from unicodedata import normalize

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

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


class ProductionForm(ScriptForm):
    thumbnail_file = forms.FileField(
        label="Imagem da thumb", required=False,
        help_text="JPG ou PNG, até 8 MB e 16 megapixels.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
    )
    remove_thumbnail = forms.BooleanField(label="Remover a imagem atual", required=False)

    class Meta(ScriptForm.Meta):
        fields = (*ScriptForm.Meta.fields, "video_title", "thumbnail_text", "thumbnail_file", "remove_thumbnail")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.thumbnail:
            self.fields.pop("remove_thumbnail")

    def clean_thumbnail_file(self):
        uploaded = self.cleaned_data.get("thumbnail_file")
        if not uploaded:
            return None
        if uploaded.size > 8 * 1024 * 1024:
            raise forms.ValidationError("A imagem deve ter até 8 MB.")
        try:
            with Image.open(uploaded, formats=["JPEG", "PNG"]) as image:
                if image.width * image.height > 16_000_000:
                    raise forms.ValidationError("A imagem deve ter até 16 megapixels.")
                image_format = image.format
                image.verify()
            uploaded.seek(0)
            with Image.open(uploaded, formats=[image_format]) as image:
                image = ImageOps.exif_transpose(image)
                if image_format == "JPEG":
                    image = image.convert("RGB")
                output = BytesIO()
                image.save(output, format=image_format)
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
            raise forms.ValidationError("Envie um arquivo JPG ou PNG válido.") from error
        extension = "jpg" if image_format == "JPEG" else "png"
        return ContentFile(output.getvalue(), name=f"thumb.{extension}")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("remove_thumbnail") and cleaned.get("thumbnail_file"):
            self.add_error("thumbnail_file", "Escolha entre substituir ou remover a imagem atual.")
        return cleaned
