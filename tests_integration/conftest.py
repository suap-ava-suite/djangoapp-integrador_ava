import os
import shutil
import subprocess
import time

import pytest
import sc4net

from integrador.models import Ambiente

MOODLE_URL = os.getenv("MOODLE_INTEGRATION_URL", "http://moodle")


def wait_for_url(url, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(2)
        try:
            # sc4net.get retorna o conteúdo decodificado por padrão
            sc4net.get(url, timeout=2)
            return True
        except Exception as e:
            print(e)
    return False


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
    """Garante que o ambiente Docker está rodando se estivermos fora dele."""
    if os.getenv("MOODLE_INTEGRATION_URL"):
        print("\nRodando dentro do Docker, pulando docker compose up.")
        if not wait_for_url(MOODLE_URL):
            pytest.fail(f"Moodle em {MOODLE_URL} não ficou pronto a tempo.")
        yield
        return

    print("\nSubindo ambiente Docker para integração...")
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        pytest.fail("docker não encontrado no PATH")

    subprocess.run(  # noqa: S603
        [docker_bin, "compose", "-f", "tests_integration/docker-compose.integration.yml", "up", "-d", "--wait"],
        check=True,
    )
    if not wait_for_url(MOODLE_URL):
        pytest.fail(f"Moodle em {MOODLE_URL} não ficou pronto a tempo.")

    yield


@pytest.fixture
def integration_ambiente(db, moodle_seed_data):
    """Cria o ambiente no Django apontando para o Moodle Docker."""

    ambiente, created = Ambiente.objects.update_or_create(
        nome="Moodle Local Docker",
        defaults={
            "url": MOODLE_URL,
            "expressao_seletora": "campus.sigla == 'ZL'",
            "local_suap_token": "test_token",
            "local_suap_active": True,
            "ordem": 0,
        },
    )
    return ambiente
