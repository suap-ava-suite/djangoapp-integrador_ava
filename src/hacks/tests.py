"""Testes unitários para a app hacks."""

from django.apps import apps
from django.test import TestCase

from hacks.apps import HacksConfig


class HacksConfigTestCase(TestCase):
    """Testes para a configuração da app hacks."""

    def test_hacks_config(self):
        """Testa nome e verbose_name da app hacks."""
        self.assertEqual(HacksConfig.name, "hacks")
        self.assertEqual(HacksConfig.verbose_name, "Hacks")
        self.assertEqual(HacksConfig.default_auto_field, "django.db.models.BigAutoField")

    def test_hacks_app_registered(self):
        """Testa se a app hacks está registrada no Django."""
        app_config = apps.get_app_config("hacks")
        self.assertIsInstance(app_config, HacksConfig)
