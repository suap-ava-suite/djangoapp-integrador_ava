import logging

from integrador.brokers.base import BaseBroker

logger = logging.getLogger(__name__)


class Sga2ToolSgaBroker(BaseBroker):
    def sync_up_enrolments(self) -> dict:
        raise NotImplementedError("Ainda não implementado.")

    def sync_down_grades(self) -> dict:
        raise NotImplementedError("Ainda não implementado.")
