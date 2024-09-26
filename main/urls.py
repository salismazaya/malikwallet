from django.urls import path, include, re_path
from main import views

urlpatterns = [
    path('', include('pwa.urls')),
    path('', views.index, name = 'index'),
    re_path(r'^supersecret/hooks/digiflazz/?$', views.pulsa_webhook, name = 'pulsa_webhook'),
    path('transfer/', views.transfer, name = 'transfer'),
    path('pulsa/', views.pulsa, name = 'pulsa'),
    path('pk/', views.pk, name = 'pk'),
    path('beams/', views.beams_auth, name = 'beams_auth'),
    re_path(r'^service-worker.js/?$', views.service_worker, name = 'service_worker'),
    path('login/', views.login, name = 'login'),
    path('pay/<int:merchant_id>/', views.pay, name = 'pay'),
    re_path(r'^supersecret/cron/?', views.cron, name = 'cron'),
    re_path(r'^supersecret/backup/?', views.backup, name = 'backup'),
    re_path(r'^api/check/?$', views.get_name),
    re_path(r'^api/pay/?$', views.pay_2),
    re_path(r'^api/balance/?$', views.get_balance),
]