from django.test import TestCase
from sc4net import get_json

from integrador.brokers.suap2local_suap import Suap2LocalSuapBroker
from integrador.models import Ambiente, Solicitacao

DEFAULT_HEADERS = {"Authentication": "Token changeme"}


class Suap2LocalSuapIntegrationTestCase(TestCase):
    """Testes de integração para o broker Suap2LocalSuap com Moodle real."""

    def test_sync_up_enrolments_real(self):
        """Testa a sincronização de matrículas com um Moodle real."""
        diario_id = 7
        payload = {
            "campus": {"id": 14, "sigla": "ZL", "descricao": "CAMPUS AVANÇADO NATAL-ZONA LESTE"},
            "curso": {"id": 12, "nome": "Tecnologia em Gestão Ambiental", "codigo": "12345"},
            "turma": {"id": 1234, "codigo": "2025.3.18.1234"},
            "componente": {"id": 15, "sigla": "MIC.AMB", "descricao": "Microbiologia Ambiental"},
            "diario": {"id": diario_id, "sigla": "MIC.AMB", "situacao": "Aberto"},
            "alunos": [
                {
                    "id": 13,
                    "nome": "Aluno Teste",
                    "email": "aluno7@example.com",
                    "matricula": "aluno7",
                    "situacao": "ativo",
                    "tipo_usuario": "Aluno",
                }
            ],
            "professores": [{"id": 157706, "nome": "João Maria", "email": "joaomaria@ifrn.edu.br", "login": "123456"}],
            "sincrono": True,
        }

        ambiente = Ambiente.objects.first() or Ambiente.objects.create(
            nome="Moodle Teste",
            url="http://moodle",
            local_suap_token="changeme",  # noqa S106
            local_suap_active=True,
        )
        solicitacao = Solicitacao.objects.create(
            ambiente=ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido=payload
        )

        broker = Suap2LocalSuapBroker(solicitacao)
        result = broker.sync_up_enrolments()

        # Verifica se o Moodle respondeu com sucesso
        self.assertIn("ambiente", result)
        self.assertEqual(result["ambiente"], "http://moodle")
        self.assertTrue("url_sala_diario" in result or "url" in result)
        if "error" in result:
            self.assertFalse(result["error"], f"Erro retornado pelo local_suap: {result['error']}")

    def test_sync_down_grades_real(self):
        """Testa a baixa de notas com um Moodle real."""
        url_prefix = "http://integrador:8000/api/baixar_notas/?campus_sigla=ZL&diario_id"

        notas1 = get_json(f"{url_prefix}=1", headers=DEFAULT_HEADERS, timeout=2)
        self.assertIsInstance(notas1, list, f"Esperava uma lista de notas, recebeu: {type(notas1)}")
        self.assertEqual(len(notas1), 0)

        # Todas as notas e completudes do curso 2 estão vazias pois só tem as matrículas
        # sem grade configurado
        notas2 = get_json(f"{url_prefix}=2", headers=DEFAULT_HEADERS, timeout=2)
        self.assertIsInstance(notas2, list, f"Esperava uma lista de notas, recebeu: {type(notas2)}")
        self.assertEqual(len(notas2), 3)
        for nota in notas2:
            self.assertIsNone(nota.get("notas"))
            self.assertIsNone(nota.get("completude"))
            self.assertEqual(f"{nota.get('matricula')} {nota.get('matricula')}", nota.get("nome_completo"))

        # Todas as notas e completudes do curso 3 estão vazias pois só tem as matrículas e atividades
        # sem grade configurado
        notas3 = get_json(f"{url_prefix}=3", headers=DEFAULT_HEADERS, timeout=2)
        self.assertIsInstance(notas3, list, f"Esperava uma lista de notas, recebeu: {type(notas3)}")
        self.assertEqual(len(notas3), 3)
        for nota in notas3:
            self.assertIsNone(nota.get("notas"))
            self.assertIsNone(nota.get("completude"))
            self.assertEqual(f"{nota.get('matricula')} {nota.get('matricula')}", nota.get("nome_completo"))

        # Todas as notas e completudes do curso 4 estão vazias pois só tem as matrículas e atividades
        # grade configurada, notas atribuídas e completude realizada
        notas4 = get_json(f"{url_prefix}=4", headers=DEFAULT_HEADERS, timeout=2)
        self.assertIsInstance(notas4, list, f"Esperava uma lista de notas, recebeu: {type(notas3)}")
        self.assertEqual(len(notas4), 3)
        esperados = {
            "aluno001": {"notas": {"N1": 1}, "completude": None},
            "aluno002": {"notas": {"N1": 70}, "completude": None},
            "aluno003": {"notas": {"N1": 100}, "completude": 100},
        }
        for nota in notas4:
            esperado = esperados.get(nota.get("matricula"), {"notas": {}, "completude": None})
            self.assertEqual(f"{nota.get('matricula')} {nota.get('matricula')}", nota.get("nome_completo"))
            self.assertEqual(nota.get("completude", "UNDEFINED"), esperado.get("completude"))
            self.assertEqual((nota.get("notas") or {}).get("N1", "UNDEFINED"), esperado["notas"]["N1"])
