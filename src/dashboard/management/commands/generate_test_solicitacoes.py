"""
Management command para gerar solicitações de teste para o dashboard.
Cria dados históricos para os últimos 12 meses.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from integrador.models import Solicitacao


class Command(BaseCommand):
    help = "Gera solicitações de teste para o dashboard"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=12,
            help="Número de meses de dados a gerar (padrão: 12)",
        )
        parser.add_argument(
            "--per-day",
            type=int,
            default=10,
            help="Número de solicitações por dia (padrão: 10)",
        )

    def handle(self, *args, **options):
        months = options["months"]
        per_day = options["per_day"]

        # Status choices
        statuses = [
            Solicitacao.Status.SUCESSO,
            Solicitacao.Status.FALHA,
            Solicitacao.Status.PROCESSANDO,
        ]

        # Gerar dados
        solicitacoes = []
        current_date = now()
        start_date = current_date - timedelta(days=30 * months)

        date = start_date
        count = 0

        while date <= current_date:
            for _ in range(per_day):
                # Pesar os status: mais sucesso, menos falhas
                status = random.choices(statuses, weights=[70, 20, 10], k=1)[0]  # noqa: S311

                solicitacao = Solicitacao(
                    timestamp=date
                    + timedelta(
                        hours=random.randint(0, 23),  # noqa: S311
                        minutes=random.randint(0, 59),  # noqa: S311
                    ),
                    status=status,
                    # Adicionar outros campos obrigatórios se necessário
                )
                solicitacoes.append(solicitacao)
                count += 1

            date += timedelta(days=1)

        # Criar em batch
        Solicitacao.objects.bulk_create(solicitacoes, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"✓ {count} solicitações de teste criadas"))
