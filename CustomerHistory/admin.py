from django.contrib import admin
from .models import Cliente, Historico, LogXML

admin.site.register(Cliente)
admin.site.register(Historico)
admin.site.register(LogXML)
