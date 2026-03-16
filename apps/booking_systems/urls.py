from django.urls import path
from .views import (
    BookingSystemConnectView,
    BookingSystemStatusView,
    ProviderListView,
    CustomerListView,
    ServiceListView,
    AppointmentListView,
)

urlpatterns = [
    path("connect/",                       BookingSystemConnectView.as_view(), name="booking-system-connect"),
    path("<int:pk>/status/",               BookingSystemStatusView.as_view(),  name="booking-system-status"),
    path("<int:pk>/providers/",            ProviderListView.as_view(),         name="booking-system-providers"),
    path("<int:pk>/customers/",            CustomerListView.as_view(),         name="booking-system-customers"),
    path("<int:pk>/services/",             ServiceListView.as_view(),          name="booking-system-services"),
    path("<int:pk>/appointments/",         AppointmentListView.as_view(),      name="booking-system-appointments"),
]
