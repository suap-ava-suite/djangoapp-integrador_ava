import copy
import logging

from integrador.brokers.base import BaseBroker
from integrador.utils import SyncError, http_get_json, http_post_json

logger = logging.getLogger(__name__)

_SYNC_UP_REQUIRED_FIELDS = {
    "campus": ["id", "sigla", "descricao"],
    "curso": ["id", "codigo", "nome"],
    "turma": ["id", "codigo"],
    "componente": ["id", "sigla", "descricao"],
    "diario": ["id", "sigla", "situacao"],
}


class Suap2LocalSuapBroker(BaseBroker):

    @property
    def moodle_base_api_url(self):
        return f"{self.solicitacao.ambiente.base_url}/local/suap/api"

    def __get_service_url(self, service: str) -> str:
        logger.debug(f"{self.moodle_base_api_url}/index.php?{service}")
        return f"{self.moodle_base_api_url}/index.php?{service}"

    def __get_json(self, service: str, **params: dict):
        querystring = "&".join([f"{k}={v}" for k, v in params.items() if v is not None]) if params is not None else ""
        result = http_get_json(f"{self.__get_service_url(service)}&{querystring}", headers=self.credentials)
        logger.debug(f"Response: {result}")
        return result

    def __post_json(self, service: str, jsonbody: dict):
        result = http_post_json(self.__get_service_url(service), jsonbody, self.credentials)
        return result

    def _validate_sync_payload(self, payload: dict) -> None:
        missing = [
            f"{field}.{sub}" if field in payload else field
            for field, subfields in _SYNC_UP_REQUIRED_FIELDS.items()
            for sub in (subfields if field in payload else [""])
            if field not in payload or sub not in payload[field]
        ]
        if missing:
            raise SyncError(
                f"Campos obrigatórios ausentes no payload de sync_up_enrolments: {', '.join(missing)}.",
                422,
            )

    def _set_restricoes(self, enviados: dict) -> None:
        def get_tipos_usuarios(ai: dict) -> str:
            tipos_usuarios = []
            if "tecnicos_administrativos" in ai and ai["tecnicos_administrativos"]:
                tipos_usuarios.append("'Servidor (Técnico-Administrativo)'")

            if "docentes" in ai and ai["docentes"]:
                tipos_usuarios.append("'Servidor (Docente)'")

            if "prestadores" in ai and ai["prestadores"]:
                tipos_usuarios.append("'Prestador de Serviço'")

            if "alunos" in ai and ai["alunos"]:
                tipos_usuarios.append("'Aluno'")
            return f"tipo_usuario in [{', '.join(tipos_usuarios)}]" if tipos_usuarios else ""

        def get_nacionalidades(ai: dict) -> str:
            return (
                "$any([m['estrangeiro'] == true and m['detalhamento']['ativo'] == true for m in outras_matriculas])"
                if ai.get("estrangeiros")
                else ""
            )

        def get_alunos(lista: list[dict[str, str]], filter: str) -> str:
            if not lista or len(lista) == 0:
                return ""
            args = [f"'{i}'" for i in lista]
            return (
                f"$any([m['tipo'] == 'aluno' and m['detalhamento']['ativo'] == true and {filter} in"
                + f" [{', '.join(args)}] for m in outras_matriculas])"
            )

        payload = enviados or {}
        if payload.get("turma") is None:
            payload["turma"] = {}

        autoinscricao = payload.get("autoinscricao") or {}

        restricoes = [
            get_tipos_usuarios(autoinscricao),
            get_nacionalidades(autoinscricao),
            get_alunos(autoinscricao.get("campi", []), "m['campus']"),
            get_alunos(autoinscricao.get("modalidades", []), "m['detalhamento']['modalidade']"),
            get_alunos(autoinscricao.get("niveis_ensino", []), "m['detalhamento']['nivel_ensino']"),
            get_alunos(autoinscricao.get("cursos", []), "m['detalhamento']['curso']"),
        ]
        payload["turma"]["restricoes"] = " and ".join([r for r in restricoes if r != ""])

        if payload["turma"].get("autoinscricao") is None:
            payload["turma"]["autoinscricao"] = payload.get("autoinscricao") is not None

    def sync_up_enrolments(self) -> dict:
        self._validate_sync_payload(self.solicitacao.recebido)
        self.solicitacao.enviado = copy.deepcopy(self.solicitacao.recebido) if self.solicitacao.recebido else {}
        self.solicitacao.enviado["solicitacao_url"] = (
            f"{self.solicitacao.site_url}/integrador/solicitacao/{self.solicitacao.id}/view/"
        )

        try:
            self.solicitacao.enviado["coortes"] = self.get_cohort()
        except Exception as e:
            raise SyncError(
                "Erro ao tentar obter as COORTES "
                + "antes mesmo de iniciar a integração com o Moodle."
                + f" Contacte um administrador. Erro: {e}.",
                getattr(e, "code", 525),
            )

        try:
            self._set_restricoes(self.solicitacao.enviado)
        except Exception as e:
            raise SyncError(
                "Erro ao tentar processar as RESTRIÇÕES do curso com autoinscrição "
                + "antes mesmo de iniciar a integraçãos o Moodle."
                + f" Contacte um administrador.Erro: {e}.",
                getattr(e, "code", 526),
            )

        try:
            self.solicitacao.save(update_fields=["enviado"])
        except Exception as e:
            raise SyncError(
                "Erro ao tentar SALVAR o payload "
                + "antes mesmo de ser enviado ao Moodle."
                + f" Contacte um administrador. Erro: {e}.",
                getattr(e, "code", 527),
            )

        result = self.__post_json("sync_up_enrolments", self.solicitacao.enviado)
        result["ambiente"] = self.solicitacao.ambiente.base_url

        for key in ["logMessages", "sala_tipo", "sincronizacao_url", "restricoes", "ids_suspensos"]:
            result.pop(key, None)
        return result

    def sync_down_grades(self) -> dict:
        return self.__get_json("sync_down_grades", diario_id=self.solicitacao.diario_id)
