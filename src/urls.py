from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from django_suap_auth.views import SuapCallbackView, SuapLoginView

admin.site.site_title = f"{settings.PROJECT_TITLE} (v{settings.PROJECT_VERSION})"
admin.site.index_title = settings.PROJECT_TITLE
admin.site.site_header = admin.site.site_title

urlpatterns = []

# Debug toolbar deve vir PRIMEIRO em modo DEBUG
if settings.DEBUG:
    try:
        if "debug_toolbar" in settings.INSTALLED_APPS:
            import debug_toolbar

            urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))
    except ModuleNotFoundError:  # pragma: no cover
        pass

urlpatterns += [
    path("admin/login/", RedirectView.as_view(url="/auth/suap/login/", query_string=True)),
    path("login/", RedirectView.as_view(url="/auth/suap/login/", query_string=True)),
    path("logout/", RedirectView.as_view(url="/auth/suap/logout/", query_string=True)),
    path("authenticate/", RedirectView.as_view(url="/auth/suap/callback/", query_string=True)),
    path("", include("integrador.urls")),  # noqa URLs do integrador ANTES do admin
    path("", include("health.urls")),  # noqa
    path("auth/suap/", include("django_suap_auth.urls")),  # noqa
    path("", admin.site.urls),  # noqa
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(
            f"{settings.ROOT_URL_PATH}media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
        re_path(
            f"{settings.ROOT_URL_PATH}static/(?P<path>.*)$",
            serve,
            {"document_root": settings.STATIC_ROOT},
        ),
    ]
