import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from sga.db.obfuscators import mask_all


def permissive_url_validator(value):
    pattern = r"^https?://[\w.-]+(:\d+)?(/.*)?$"
    if not re.match(pattern, value):
        raise ValidationError("Informe uma URL válidaaa.")


class PermissiveURLField(models.URLField):
    default_validators = [permissive_url_validator]

    def formfield(self, **kwargs):
        return models.CharField.formfield(self, **{"form_class": forms.CharField, **kwargs})


class ObfuscatedCharField(models.CharField):
    def __init__(self, *args, obfuscator=mask_all, **kwargs):
        self.obfuscator = obfuscator
        super().__init__(*args, **kwargs)

    def get_obfuscated_value(self, value):
        if value is None:
            return None
        if self.obfuscator is not None:
            return self.obfuscator(value)
        return "****" + value[-4:]

    def from_db_value(self, value, expression, connection):
        return self.get_obfuscated_value(value)

    def to_python(self, value):
        return self.get_obfuscated_value(value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.obfuscator is not None:
            kwargs["obfuscator"] = self.obfuscator
        return name, path, args, kwargs
