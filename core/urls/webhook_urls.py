from django.urls import path

from core.views_webhooks import bot_comercial_webhook, whatsapp_webhook

urlpatterns = [
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('webhook/ia-bot-comercial/', bot_comercial_webhook, name='bot_comercial_webhook'),
]
