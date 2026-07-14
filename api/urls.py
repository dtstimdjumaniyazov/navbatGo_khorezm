from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api import views

router = DefaultRouter()
router.register("service-points", views.ServicePointViewSet)
router.register("bays", views.BayViewSet)
router.register("services", views.ServiceViewSet)
router.register("clients", views.ClientViewSet)
router.register("appointments", views.AppointmentViewSet)

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("auth/telegram/start/", views.TelegramLoginStartView.as_view(), name="tg-login-start"),
    path("auth/telegram/poll/", views.TelegramLoginPollView.as_view(), name="tg-login-poll"),
    path("profile/", views.MyProfileView.as_view(), name="my-profile"),
    path("profile/media/", views.MyMediaView.as_view(), name="my-media"),
    path("profile/media/<uuid:pk>/", views.MyMediaDetailView.as_view(), name="my-media-detail"),
    path("public/service-points/", views.PublicServicePointListView.as_view(), name="public-list"),
    path("public/service-points/<uuid:pk>/", views.PublicProfileView.as_view(), name="public-profile"),
    path("my/appointments/", views.MyAppointmentsView.as_view(), name="my-appointments"),
    path("my/appointments/<uuid:pk>/cancel/", views.MyAppointmentCancelView.as_view(), name="my-appt-cancel"),
    path("my/settings/", views.MySettingsView.as_view(), name="my-settings"),
    path("notifications/push-token/", views.RegisterPushTokenView.as_view(), name="push-token"),
    path("slots/", views.SlotsView.as_view(), name="slots"),
    path("", include(router.urls)),
]
