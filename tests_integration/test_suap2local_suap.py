from unittest import TestCase

import pytest
import requests

DEFAULT_HEADERS = {"Authentication": "Token changeme"}


@pytest.mark.django_db
@pytest.mark.usefixtures("integration_ambiente")
class Suap2LocalSuapIntegrationTestCase(TestCase):
    """Testes de integração para o broker Suap2LocalSuap com Moodle real."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, integration_ambiente):
        self.integration_ambiente = integration_ambiente

    # def test_sync_up_enrolments_real(self):
    #     """Testa a sincronização de matrículas com um Moodle real."""
    #     diario_id = self.moodle_seed_data["diario_id"]
    #     payload = {
    #         "campus": {"id": 14, "sigla": "ZL", "descricao": "CAMPUS AVANÇADO NATAL-ZONA LESTE"},
    #         "curso": {"id": 12, "nome": "Tecnologia em Gestão Ambiental", "codigo": "12345"},
    #         "turma": {"id": 1234, "codigo": "2025.3.18.1234"},
    #         "componente": {"id": 15, "sigla": "MIC.AMB", "descricao": "Microbiologia Ambiental"},
    #         "diario": {"id": diario_id, "sigla": "MIC.AMB", "situacao": "Aberto"},
    #         "alunos": [
    #             {
    #                 "id": 13,
    #                 "nome": "Aluno Teste",
    #                 "email": self.moodle_seed_data["student_username"] + "@example.com",
    #                 "matricula": self.moodle_seed_data["student_username"],
    #                 "situacao": "ativo",
    #             }
    #         ],
    #         "professores": [
    #             {
    #                 "id": 157706,
    #                 "nome": "João Maria",
    #                 "email": "joaomaria@ifrn.edu.br",
    #                 "login": "123456"
    #             }
    #         ],
    #         "sincrono": True,
    #     }

    #     solicitacao = Solicitacao.objects.create(
    #         ambiente=self.integration_ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido=payload
    #     )

    #     broker = Suap2LocalSuapBroker(solicitacao)
    #     result = broker.sync_up_enrolments()

    #     # Verifica se o Moodle respondeu com sucesso
    #     self.assertIn("ambiente", result)
    #     self.assertEqual(result["ambiente"], "http://moodle")
    #     self.assertTrue("url_sala_diario" in result or "url" in result)
    #     if "error" in result:
    #         self.assertFalse(result["error"], f"Erro retornado pelo local_suap: {result['error']}")

    def test_sync_down_grades_real(self):
        """Testa a baixa de notas com um Moodle real."""
        print(
            requests.get(
                "http://integrador:8000/api/baixar_notas/?campus_sigla=ZL&diario_id=4",
                headers=DEFAULT_HEADERS,
                timeout=2,
            )
        )

        # diario_id = self.moodle_seed_data["diario_id"]
        # student_username = self.moodle_seed_data["student_username"]

        # solicitacao = Solicitacao.objects.create(
        #     ambiente=self.integration_ambiente, operacao=Solicitacao.Operacao.SYNC_DOWN_NOTAS, diario_id=diario_id
        # )

        # broker = Suap2LocalSuapBroker(solicitacao)
        # result = broker.sync_down_grades()

        # # O local_suap retorna uma lista de dicionários de notas
        # self.assertIsInstance(result, list, f"Esperava uma lista de notas, recebeu: {type(result)}")

        # # Busca a nota do aluno que inserimos no seed
        # aluno_nota = next((item for item in result if item.get("matricula") == student_username), None)

        # self.assertIsNotNone(aluno_nota, f"Nota do aluno {student_username} não encontrada no retorno: {result}")

        # # No real local_suap as notas vêm no objeto 'notas' indexado pelo idnumber do item
        # self.assertIn("notas", aluno_nota)
        # self.assertIsNotNone(
        #     aluno_nota["notas"], f"Notas vieram como None para o aluno {student_username}. Retorno: {result}"
        # )
        # self.assertIn("N1", aluno_nota["notas"])
        # self.assertEqual(float(aluno_nota["notas"]["N1"]), 85.0)
