"""
Classe responsável pelo carregamento e armazenamento de dados do dashboard.
Isola a lógica de negócio da view.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils.timezone import now

from cohort.models import Cohort, Enrolment, MoodleUser, Role
from integrador.models import Ambiente, Solicitacao

logger = logging.getLogger(__name__)

# Configuração de cache
CACHE_ENABLED = getattr(settings, "DASHBOARD_CACHE_ENABLED", True)
CACHE_TIMEOUT = getattr(settings, "DASHBOARD_CACHE_TIMEOUT", 300)
CACHE_KEY = "admin_dashboard_data"


class DashboardStorage:
    """Gerencia o carregamento e cache dos dados do dashboard."""

    def __init__(self):
        self.data = {
            "ambientes_total": 0,
            "ambientes_ativos": 0,
            "ambientes_com_erro": 0,
            "coortes_total": 0,
            "coortes_ativas": 0,
            "coortes_inativas": 0,
            "enrolments_total": 0,
            "papeis_total": 0,
            "papeis_ativos": 0,
            "papeis_inativos": 0,
            "usuarios_total": 0,
            "usuarios_ativos": 0,
            "grupos_total": 0,
            "solicitacoes_24h": 0,
            "solicitacoes_sucesso": 0,
            "solicitacoes_falha": 0,
            "solicitacoes_processando": 0,
            "total_solicitacoes": 0,
            "taxa_sucesso": 0,
            "solicitacoes_series": [],
        }

    def get_context(self):
        """
        Retorna o contexto do dashboard.
        Tenta usar cache, caso contrário carrega dados frescos.
        """
        if CACHE_ENABLED:
            cached_data = cache.get(CACHE_KEY)
            if cached_data is not None:
                logger.debug("Dashboard data carregado do cache")
                return cached_data

        self._load_data()

        if CACHE_ENABLED:
            cache.set(CACHE_KEY, self.data, CACHE_TIMEOUT)
            logger.debug(f"Dashboard data armazenado em cache por {CACHE_TIMEOUT}s")
        else:
            logger.debug("Cache desabilitado - dados não foram armazenados")

        return self.data

    def get_auth_context(self):
        """Retorna o contexto do dashboard da aplicação Auth."""
        try:
            usuarios_total = User.objects.count()
            usuarios_ativos = User.objects.filter(is_active=True).count()
            usuarios_inativos = usuarios_total - usuarios_ativos
            usuarios_equipe = User.objects.filter(is_staff=True).count()

            grupos_total = Group.objects.count()
            grupos_queryset = Group.objects.annotate(num_users=Count("user")).order_by("-num_users", "name")
            grupos_detalhe = [
                {"name": grupo.name, "usuarios_count": grupo.num_users}
                for grupo in grupos_queryset
            ]

            return {
                "usuarios_total": usuarios_total,
                "usuarios_ativos": usuarios_ativos,
                "usuarios_inativos": usuarios_inativos,
                "usuarios_equipe": usuarios_equipe,
                "grupos_total": grupos_total,
                "grupos_detalhe": grupos_detalhe,
            }
        except Exception as e:
            logger.error(f"Erro ao carregar contexto de auth: {e}", exc_info=True)
            return {
                "usuarios_total": 0,
                "usuarios_ativos": 0,
                "usuarios_inativos": 0,
                "usuarios_equipe": 0,
                "grupos_total": 0,
                "grupos_detalhe": [],
            }

    def get_cohort_context(self, top_n=5):
        """Retorna o contexto do dashboard da aplicação Cohort."""
        try:
            coortes_total = Cohort.objects.count()
            coortes_ativas = Cohort.objects.filter(active=True).count()
            coortes_inativas = coortes_total - coortes_ativas
            coortes_top_usuarios = list(
                Cohort.objects.annotate(num_users=Count("enrolments"))
                .order_by("-num_users", "name")
                .values("name", "num_users")[:top_n]
            )

            papeis_total = Role.objects.count()
            papeis_ativos = Role.objects.filter(active=True).count()
            papeis_inativos = papeis_total - papeis_ativos
            papeis_top_coortes = list(
                Role.objects.annotate(num_cohorts=Count("cohort_roles"))
                .order_by("-num_cohorts", "name")
                .values("name", "num_cohorts")[:top_n]
            )
            papeis_top_usuarios = list(
                Role.objects.annotate(num_users=Count("cohort_roles__enrolments"))
                .order_by("-num_users", "name")
                .values("name", "num_users")[:top_n]
            )

            moodle_usuarios_total = MoodleUser.objects.count()
            moodle_usuarios_sincronizar = MoodleUser.objects.filter(active=True).count()
            moodle_usuarios_top_vinculos = list(
                MoodleUser.objects.annotate(num_vinculos=Count("enrolments"))
                .order_by("-num_vinculos", "fullname")
                .values("fullname", "login", "num_vinculos")[:top_n]
            )

            return {
                "coortes_total": coortes_total,
                "coortes_ativas": coortes_ativas,
                "coortes_inativas": coortes_inativas,
                "coortes_top_usuarios": coortes_top_usuarios,
                "papeis_total": papeis_total,
                "papeis_ativos": papeis_ativos,
                "papeis_inativos": papeis_inativos,
                "papeis_top_coortes": papeis_top_coortes,
                "papeis_top_usuarios": papeis_top_usuarios,
                "moodle_usuarios_total": moodle_usuarios_total,
                "moodle_usuarios_sincronizar": moodle_usuarios_sincronizar,
                "moodle_usuarios_top_vinculos": moodle_usuarios_top_vinculos,
            }
        except Exception as e:
            logger.error(f"Erro ao carregar contexto de cohort: {e}", exc_info=True)
            return {
                "coortes_total": 0,
                "coortes_ativas": 0,
                "coortes_inativas": 0,
                "coortes_top_usuarios": [],
                "papeis_total": 0,
                "papeis_ativos": 0,
                "papeis_inativos": 0,
                "papeis_top_coortes": [],
                "papeis_top_usuarios": [],
                "moodle_usuarios_total": 0,
                "moodle_usuarios_sincronizar": 0,
                "moodle_usuarios_top_vinculos": [],
            }

    def get_integrador_context(self):
        """Retorna o contexto do dashboard da aplicação Integrador."""
        context = self.get_context()
        return {
            "ambientes_total": context.get("ambientes_total", 0),
            "ambientes_ativos": context.get("ambientes_ativos", 0),
            "ambientes_com_erro": context.get("ambientes_com_erro", 0),
            "solicitacoes_24h": context.get("solicitacoes_24h", 0),
            "solicitacoes_sucesso": context.get("solicitacoes_sucesso", 0),
            "solicitacoes_falha": context.get("solicitacoes_falha", 0),
            "solicitacoes_processando": context.get("solicitacoes_processando", 0),
            "taxa_sucesso": context.get("taxa_sucesso", 0),
            "total_solicitacoes": context.get("total_solicitacoes", 0),
            "solicitacoes_series": context.get("solicitacoes_series", []),
        }

    def _load_data(self):
        """Carrega todos os dados do dashboard."""
        self._load_ambientes()
        self._load_coortes()
        self._load_papeis()
        self._load_usuarios()
        self._load_solicitacoes()
        self._load_series_temporal()

    def _load_ambientes(self):
        """Carrega dados de ambientes."""
        try:
            self.data["ambientes_total"] = Ambiente.objects.count()
            self.data["ambientes_ativos"] = Ambiente.objects.filter(
                Q(local_suap_active=True) | Q(tool_sga_active=True)
            ).count()
            self.data["ambientes_com_erro"] = sum(
                1
                for ambiente in Ambiente.objects.filter(Q(local_suap_active=True) | Q(tool_sga_active=True))
                if not ambiente.valid_expressao_seletora
            )
            logger.info(
                f"Ambientes carregados: total={self.data['ambientes_total']}, ativos={self.data['ambientes_ativos']}"
            )
        except Exception as e:
            logger.error(f"Erro ao carregar ambientes: {e}", exc_info=True)

    def _load_coortes(self):
        """Carrega dados de coortes."""
        try:
            self.data["coortes_total"] = Cohort.objects.count()
            self.data["coortes_ativas"] = Cohort.objects.filter(active=True).count()
            self.data["coortes_inativas"] = self.data["coortes_total"] - self.data["coortes_ativas"]
            self.data["enrolments_total"] = Enrolment.objects.count()
            logger.info(f"Coortes carregadas: total={self.data['coortes_total']}, ativas={self.data['coortes_ativas']}")
        except Exception as e:
            logger.error(f"Erro ao carregar coortes: {e}", exc_info=True)

    def _load_papeis(self):
        """Carrega dados de papéis."""
        try:
            self.data["papeis_total"] = Role.objects.count()
            self.data["papeis_ativos"] = Role.objects.filter(active=True).count()
            self.data["papeis_inativos"] = self.data["papeis_total"] - self.data["papeis_ativos"]
            logger.info(f"Papéis carregados: total={self.data['papeis_total']}, ativos={self.data['papeis_ativos']}")
        except Exception as e:
            logger.error(f"Erro ao carregar papéis: {e}", exc_info=True)

    def _load_usuarios(self):
        """Carrega dados de usuários e grupos."""
        try:
            self.data["usuarios_total"] = User.objects.count()
            self.data["usuarios_ativos"] = User.objects.filter(is_active=True).count()
            self.data["grupos_total"] = Group.objects.count()
            logger.info(
                f"Usuários carregados: total={self.data['usuarios_total']}, ativos={self.data['usuarios_ativos']}"
            )
        except Exception as e:
            logger.error(f"Erro ao carregar usuários: {e}", exc_info=True)

    def _load_solicitacoes(self):
        """Carrega dados agregados de solicitações."""
        try:
            agora = now()
            ontem = agora - timedelta(hours=24)

            self.data["solicitacoes_24h"] = Solicitacao.objects.filter(timestamp__gte=ontem).count()
            self.data["solicitacoes_sucesso"] = Solicitacao.objects.filter(status="S").count()
            self.data["solicitacoes_falha"] = Solicitacao.objects.filter(status="F").count()
            self.data["solicitacoes_processando"] = Solicitacao.objects.filter(status="P").count()

            self.data["total_solicitacoes"] = (
                self.data["solicitacoes_sucesso"]
                + self.data["solicitacoes_falha"]
                + self.data["solicitacoes_processando"]
            )

            if self.data["total_solicitacoes"] > 0:
                self.data["taxa_sucesso"] = round(
                    (self.data["solicitacoes_sucesso"] / self.data["total_solicitacoes"]) * 100
                )

            logger.info(
                f"Solicitações carregadas: 24h={self.data['solicitacoes_24h']}, "
                f"sucesso={self.data['solicitacoes_sucesso']}"
            )
        except Exception as e:
            logger.error(f"Erro ao carregar solicitações agregadas: {e}", exc_info=True)

    def _load_series_temporal(self):
        """Carrega série temporal histórica de solicitações agregada por mês/ano."""
        try:
            series_queryset = (
                Solicitacao.objects.all()
                .annotate(month=TruncMonth("timestamp"))
                .values("month")
                .annotate(
                    total=Count("id"),
                    sucesso=Count("id", filter=Q(status=Solicitacao.Status.SUCESSO)),
                    falha=Count("id", filter=Q(status=Solicitacao.Status.FALHA)),
                    processando=Count("id", filter=Q(status=Solicitacao.Status.PROCESSANDO)),
                )
                .order_by("month")
            )

            self.data["solicitacoes_series"] = []
            for item in series_queryset:
                # TruncMonth retorna o primeiro dia do mês
                if item["month"]:
                    month_date = item["month"]
                    # Formatar como YYYY-MM para o gráfico
                    formatted_date = month_date.strftime("%Y/%m")
                    self.data["solicitacoes_series"].append(
                        {
                            "date": formatted_date,
                            "total": item["total"],
                            "sucesso": item["sucesso"],
                            "falha": item["falha"],
                            "processando": item["processando"],
                        }
                    )

            logger.info(f"Série temporal histórica carregada: {len(self.data['solicitacoes_series'])} meses")
        except Exception as e:
            logger.error(f"Erro ao carregar série temporal: {e}", exc_info=True)
            self.data["solicitacoes_series"] = []
