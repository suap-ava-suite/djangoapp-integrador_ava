from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from sga.db.obfuscators import mask_all

OBFUSCATION_MASK = "****"
OBFUSCATION_VISIBLE_SUFFIX_LENGTH = 4


def default_obfuscation(value):
    if len(value) >= OBFUSCATION_VISIBLE_SUFFIX_LENGTH:
        return OBFUSCATION_MASK + value[-OBFUSCATION_VISIBLE_SUFFIX_LENGTH:]
    return OBFUSCATION_MASK


def permissive_url_validator(value):
    if value is None:
        return None
    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(value)
    except ValidationError:
        raise ValidationError(_("Informe uma URL válida."))


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
        return default_obfuscation(value)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.obfuscator != mask_all:
            kwargs["obfuscator"] = self.obfuscator
        return name, path, args, kwargs
