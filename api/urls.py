from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api import views

router = DefaultRouter()
router.register("service-points", views.ServicePointViewSet)
router.register("bays", views.BayViewSet)
router.register("services", views.ServiceViewSet)
router.register("clients", views.ClientViewSet)
router.register("appointments", views.AppointmentViewSet)

urlpatterns = [
    path("slots/", views.SlotsView.as_view(), name="slots"),
    path("", include(router.urls)),
]
