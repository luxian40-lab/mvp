import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','mvp_project.settings')
import django
django.setup()
from django.test import Client
c = Client()
resp = c.post('/webhook/whatsapp/', {
    'From':'whatsapp:+573026480629',
    'To':'whatsapp:+14155238886',
    'Body':'B',
    'MessageSid':'testsid123',
    'NumMedia':'0'
})
print('STATUS', resp.status_code)
print(resp.content.decode('utf-8'))
