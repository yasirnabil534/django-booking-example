from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Booking Systems API
    path("api/booking-systems/", include("apps.booking_systems.urls")),

    # OpenAPI schema + Swagger UI + ReDoc
    path("api/schema/",         SpectacularAPIView.as_view(),        name="schema"),
    path("api/docs/",           SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/",     SpectacularRedocView.as_view(url_name="schema"),   name="redoc"),
]
