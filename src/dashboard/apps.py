from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name: str = "dashboard"
    verbose_name: str = "Dashboard"
    icon: str = "fa fa-dashboard"

    def ready(self):
        """
        Executado quando o Django está pronto.
        Aqui registramos o dashboard customizado no admin.
        """
        from django.contrib import admin

        from .admin_views import admin_app_index_dashboard, admin_index_dashboard

        # Registra as views personalizadas para a home e índices de aplicações no admin
        admin.site.index = admin_index_dashboard
        admin.site.app_index = admin_app_index_dashboard
