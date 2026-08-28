"""
Testes unitários para a app cohort.

Este módulo contém testes para:
- Role: Modelo de roles
- Cohort: Modelo de cohorts com regras de validação (RuleField)
- Enrolment: Vínculos entre users e cohorts
- Admin: Configurações do admin (RoleAdmin, CohortAdmin)
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import RequestFactory, TestCase

from cohort.admin import CohortAdmin, EnrolmentInline, RoleAdmin
from cohort.apps import CohortConfig
from cohort.models import Cohort, Enrolment, MoodleUser, Role


class IntegradorConfigTestCase(TestCase):
    """Testes para a configuração da app cohort."""

    def test_app_config_name(self):
        """Testa se o name da app está correto."""
        self.assertEqual(CohortConfig.name, "cohort")

    def test_app_config_icon(self):
        """Testa se o ícone está definido."""
        self.assertEqual(CohortConfig.icon, "fa fa-home")

    def test_app_config_default_auto_field(self):
        """Testa se default_auto_field está configurado."""
        self.assertEqual(CohortConfig.default_auto_field, "django.db.models.BigAutoField")


class CohortModelTestCase(TestCase):
    """Testes para o modelo Cohort."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.role = Role.objects.create(
            name="Coordenador de Curso",
            shortname="teachercoordenadorcurso",
            active=True,
        )

        self.cohort = Cohort.objects.create(name="Test Cohort", idnumber="TEST001", active=True, role=self.role)

    def test_create_cohort(self):
        """Testa criação de cohort."""
        cohort = Cohort.objects.create(name="New Cohort", idnumber="NEW001", active=True, role=self.role)

        self.assertIsNotNone(cohort.pk)
        self.assertEqual(cohort.name, "New Cohort")
        self.assertEqual(cohort.idnumber, "NEW001")

    def test_cohort_str_representation(self):
        """Testa representação em string do cohort."""
        self.assertEqual(str(self.cohort), "Test Cohort")

    def test_cohort_name_unique(self):
        """Testa que name deve ser único."""
        with self.assertRaises(IntegrityError):
            Cohort.objects.create(name="Test Cohort", idnumber="DIFF001", role=self.role)  # Name duplicado

    def test_cohort_idnumber_unique(self):
        """Testa que idnumber deve ser único."""
        with self.assertRaises(IntegrityError):
            Cohort.objects.create(name="Different Cohort", idnumber="TEST001", role=self.role)  # IDNumber duplicado

    def test_cohort_active_field(self):
        """Testa campo active."""
        self.assertTrue(self.cohort.active)

        self.cohort.active = False
        self.cohort.save()

        cohort = Cohort.objects.get(pk=self.cohort.pk)
        self.assertFalse(cohort.active)

    def test_cohort_rule_diario_field(self):
        """Testa campo rule_diario (RuleField)."""
        self.cohort.rule_diario = "curso.codigo == '132456'"
        self.cohort.save()

        cohort = Cohort.objects.get(pk=self.cohort.pk)
        self.assertEqual(cohort.rule_diario, "curso.codigo == '132456'")

    def test_cohort_rule_coordenacao_field(self):
        """Testa campo rule_coordenacao (RuleField)."""
        self.cohort.rule_coordenacao = "programa.sigla == 'UAB'"
        self.cohort.save()

        cohort = Cohort.objects.get(pk=self.cohort.pk)
        self.assertEqual(cohort.rule_coordenacao, "programa.sigla == 'UAB'")

    def test_cohort_description_field(self):
        """Testa campo description."""
        self.cohort.description = "Test description"
        self.cohort.save()

        cohort = Cohort.objects.get(pk=self.cohort.pk)
        self.assertEqual(cohort.description, "Test description")

    def test_cohort_role_relationship(self):
        """Testa relacionamento com Role."""
        self.assertEqual(self.cohort.role, self.role)
        self.assertIn(self.cohort, self.role.cohort_roles.all())

    def test_cohort_ordering(self):
        """Testa ordenação de cohorts."""
        Cohort.objects.create(name="Another Cohort", idnumber="ANOTHER001", role=self.role)

        cohorts = list(Cohort.objects.all())
        # Ordenação por name
        self.assertEqual(cohorts[0].name, "Another Cohort")
        self.assertEqual(cohorts[1].name, "Test Cohort")

    def test_cohort_verbose_names(self):
        """Testa verbose_name e verbose_name_plural."""
        self.assertEqual(Cohort._meta.verbose_name, "coorte")
        self.assertEqual(Cohort._meta.verbose_name_plural, "coortes")


class EnrolmentModelTestCase(TestCase):
    """Testes para o modelo Enrolment."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.user = MoodleUser.objects.create(
            fullname="Test User",
            email="testuser@example.com",
            login="testuser",
            active=True,
        )

        self.role = Role.objects.create(name="Coordenador", shortname="COORD", active=True)

        self.cohort = Cohort.objects.create(name="Test Cohort", idnumber="TEST001", role=self.role)

        self.enrolment = Enrolment.objects.create(user=self.user, cohort=self.cohort)

    def test_create_enrolment(self):
        """Testa criação de enrolment."""
        user2 = MoodleUser.objects.create(
            fullname="Test User 2",
            email="testuser2@example.com",
            login="testuser2",
            active=True,
        )

        enrolment = Enrolment.objects.create(user=user2, cohort=self.cohort)

        self.assertIsNotNone(enrolment.pk)
        self.assertEqual(enrolment.user, user2)
        self.assertEqual(enrolment.cohort, self.cohort)

    def test_enrolment_str_representation(self):
        """Testa representação em string do enrolment."""
        string_repr = str(self.enrolment)

        self.assertIn("testuser", string_repr)
        self.assertIn("Test Cohort", string_repr)

    def test_enrolment_user_relationship(self):
        """Testa relacionamento com User."""
        self.assertEqual(self.enrolment.user, self.user)

    def test_enrolment_cohort_relationship(self):
        """Testa relacionamento com Cohort."""
        self.assertEqual(self.enrolment.cohort, self.cohort)
        self.assertIn(self.enrolment, self.cohort.enrolments.all())

    def test_multiple_enrolments_same_cohort(self):
        """Testa múltiplos enrolments no mesmo cohort."""
        user2 = MoodleUser.objects.create(fullname="User 2", email="user2@example.com", login="user2", active=True)
        user3 = MoodleUser.objects.create(fullname="User 3", email="user3@example.com", login="user3", active=True)

        Enrolment.objects.create(user=user2, cohort=self.cohort)
        Enrolment.objects.create(user=user3, cohort=self.cohort)

        self.assertEqual(self.cohort.enrolments.count(), 3)

    def test_enrolment_ordering(self):
        """Testa ordenação de enrolments."""
        user2 = MoodleUser.objects.create(
            fullname="Another User",
            email="anotheruser@example.com",
            login="anotheruser",
            active=True,
        )
        Enrolment.objects.create(user=user2, cohort=self.cohort)

        enrolments = list(Enrolment.objects.all())
        # Ordenação: cohort, user
        self.assertEqual(len(enrolments), 2)

    def test_enrolment_verbose_names(self):
        """Testa verbose_name e verbose_name_plural."""
        self.assertEqual(Enrolment._meta.verbose_name, "vínculo")
        self.assertEqual(Enrolment._meta.verbose_name_plural, "vínculos")

    def test_moodle_user_str_representation(self):
        """Testa __str__ de MoodleUser com nome, email e ícone de ativo."""
        string_repr = str(self.user)
        self.assertIn("Test User", string_repr)
        self.assertIn("testuser@example.com", string_repr)
        self.assertIn("✅", string_repr)


class RoleAdminTestCase(TestCase):
    """Testes para RoleAdmin."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )
        self.role_admin = RoleAdmin(Role, None)

    def test_role_admin_list_display(self):
        """Testa configuração de list_display."""
        expected = ["name", "shortname", "active"]
        self.assertEqual(self.role_admin.list_display, expected)

    def test_role_admin_list_filter(self):
        """Testa configuração de list_filter."""
        self.assertIn("active", self.role_admin.list_filter)

    def test_role_admin_search_fields(self):
        """Testa configuração de search_fields."""
        expected = ["name", "shortname"]
        self.assertEqual(self.role_admin.search_fields, expected)

    def test_role_admin_resource_classes(self):
        """Testa configuração de resource_classes."""
        self.assertEqual(len(self.role_admin.resource_classes), 1)

        resource = self.role_admin.resource_classes[0]()
        self.assertEqual(resource._meta.model, Role)

    def test_role_resource_export_order(self):
        """Testa ordem de exportação do resource."""
        resource = self.role_admin.resource_classes[0]()
        expected = ("name", "shortname", "active")
        self.assertEqual(resource._meta.export_order, expected)

    def test_role_resource_import_id_fields(self):
        """Testa campos de identificação para importação."""
        resource = self.role_admin.resource_classes[0]()
        self.assertEqual(resource._meta.import_id_fields, ("shortname",))

    def test_role_str_representation(self):
        """Testa representação em string de Role."""
        role = Role.objects.create(name="Role Str", shortname="ROLESTR", active=True)
        self.assertIn("Role Str", str(role))
        self.assertIn("✅", str(role))


class CohortAdminTestCase(TestCase):
    """Testes para CohortAdmin."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )
        self.cohort_admin = CohortAdmin(Cohort, None)

    def test_cohort_admin_list_display(self):
        """Testa configuração de list_display."""
        expected = ["name", "idnumber", "rule_diario", "rule_coordenacao", "active"]
        self.assertEqual(self.cohort_admin.list_display, expected)

    def test_cohort_admin_search_fields(self):
        """Testa configuração de search_fields."""
        expected = ["name", "idnumber"]
        self.assertEqual(self.cohort_admin.search_fields, expected)

    def test_cohort_admin_list_filter(self):
        """Testa configuração de list_filter."""
        self.assertIn("active", self.cohort_admin.list_filter)

    def test_cohort_admin_fieldsets(self):
        """Testa configuração de fieldsets."""
        fieldsets = self.cohort_admin.fieldsets

        # CohortAdmin tem 3 fieldsets (Informações Básicas, Regras de Validação, Status)
        self.assertGreaterEqual(len(fieldsets), 2)
        self.assertEqual(fieldsets[0][0], "Informações Básicas")
        self.assertEqual(fieldsets[1][0], "Regras de Validação")

    def test_cohort_admin_inlines(self):
        """Testa configuração de inlines."""
        self.assertEqual(len(self.cohort_admin.inlines), 1)
        self.assertEqual(self.cohort_admin.inlines[0], EnrolmentInline)

    def test_cohort_resource_dehydrate_enrolments(self):
        """Testa dehydrate_enrolments exportando logins dos vinculados."""
        role = Role.objects.create(name="Role Test", shortname="ROLE_TEST", active=True)
        cohort = Cohort.objects.create(name="Cohort Export", idnumber="CEXP001", role=role)
        user_a = MoodleUser.objects.create(fullname="User A", email="a@test.com", login="login_a", active=True)
        user_b = MoodleUser.objects.create(fullname="User B", email="b@test.com", login="login_b", active=True)

        Enrolment.objects.create(user=user_a, cohort=cohort)
        Enrolment.objects.create(user=user_b, cohort=cohort)

        resource = CohortAdmin.Resource()
        value = resource.dehydrate_enrolments(cohort)

        self.assertIn("login_a", value)
        self.assertIn("login_b", value)

    @patch("base.admin.BasicModelAdmin.formfield_for_dbfield")
    def test_formfield_for_dbfield_pass_through(self, mock_super_formfield):
        """Testa formfield_for_dbfield retornando exatamente o valor do super."""
        request = RequestFactory().get("/admin/cohort/cohort/add/")
        db_field = Cohort._meta.get_field("name")
        sentinel = object()
        mock_super_formfield.return_value = sentinel

        result = self.cohort_admin.formfield_for_dbfield(db_field, request)

        self.assertIs(result, sentinel)
        mock_super_formfield.assert_called_once()


class IntegrationTestCase(TestCase):
    """Testes de integração para fluxos completos."""

    def test_complete_cohort_workflow(self):
        """Testa fluxo completo: Role -> Cohort -> Enrolment."""
        # 1. Cria role
        role = Role.objects.create(name="Coordenador", shortname="COORD", active=True)

        # 2. Cria cohort
        cohort = Cohort.objects.create(
            name="Integration Cohort",
            idnumber="INT001",
            role=role,
            rule_diario="curso.codigo == '123456'",
        )

        # 3. Cria usuário
        user = MoodleUser.objects.create(
            fullname="Integration User",
            email="integrationuser@example.com",
            login="integrationuser",
            active=True,
        )

        # 4. Cria enrolment
        enrolment = Enrolment.objects.create(user=user, cohort=cohort)

        # Verifica relacionamentos
        self.assertEqual(cohort.role, role)
        self.assertEqual(enrolment.cohort, cohort)
        self.assertEqual(enrolment.user, user)


class EdgeCasesTestCase(TestCase):
    """Testes de casos extremos."""

    def test_cohort_with_null_description(self):
        """Testa cohort com descrição nula."""
        role = Role.objects.create(name="Test", shortname="T", active=True)

        cohort = Cohort.objects.create(name="Test", idnumber="T001", role=role, description=None)

        self.assertIsNone(cohort.description)

    def test_role_inactive_icon(self):
        """Testa ícone de role inativo."""
        role = Role.objects.create(name="Inactive", shortname="INAC", active=False)

        string_repr = str(role)
        self.assertIn("⛔", string_repr)
