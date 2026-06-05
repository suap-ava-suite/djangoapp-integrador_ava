import logging
import os
import sys
import time

import psycopg

from settings import DATABASES, DEBUG, DEVELOPMENT


def _wait_db(db):
    connected = False
    connection = None
    while not connected:
        try:
            connection = psycopg.connect(
                dbname=db["NAME"],
                user=db["USER"],
                password=db["PASSWORD"],
                host=db["HOST"],
                port=db["PORT"],
            )
            connected = not connection.closed
        except Exception:  # pragma: no cover
            logging.info(
                f"Banco {db['HOST']} : {db['PORT']} / {db['NAME']} indisponível, aguardando 3s para nova tentativa"
            )
            time.sleep(3)  # pragma: no cover
        finally:
            if connection and not connection.closed:
                connection.close()
    logging.info(f"SUCCESS: Banco {db['HOST']} : {db['PORT']} / {db['NAME']} está disponível")


def start_debug():
    if DEBUG:
        try:
            import debugpy
            from django.core.management import execute_from_command_line

            debugpy.listen(("0.0.0.0", 12345))  # noqa: S104
        except Exception:  # pragma: no cover
            logging.debug("Nao foi possivel iniciar debugpy")


def start_dev_env():
    if DEVELOPMENT:
        from integrador.models import Ambiente

        Ambiente.objects.update_or_create(
            nome="Local dev",
            defaults={
                "url": "http://moodle",
                "expressao_seletora": "campus['sigla'] != 'QQ'",
                "ordem": 0,
                "local_suap_token": "changeme",
                "local_suap_active": True,
            },
        )


def boot():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError("ops!") from exc

    _wait_db(DATABASES["default"])
    execute_from_command_line([sys.argv[0], "migrate"])

    start_dev_env()
