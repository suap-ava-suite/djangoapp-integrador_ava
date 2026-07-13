from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from .apps import IntegradorConfig
from .views import sync_down_grades, sync_up_enrolments

app_name = IntegradorConfig.name


# APIs públicas autenticadas por token são marcadas como csrf_exempt
urlpatterns = [
    path("api/enviar_diarios/", csrf_exempt(sync_up_enrolments), name="api_sync_up_enrolments"),
    path("api/baixar_notas/", csrf_exempt(sync_down_grades), name="api_sync_down_grades"),
]
