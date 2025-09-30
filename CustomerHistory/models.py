from django.db import models


class Cliente(models.Model):
    cliente_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.cliente_id


class Historico(models.Model):
    cliente = models.ForeignKey(Cliente, related_name='historicos', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=100, blank=True, null=True)
    data = models.CharField(max_length=20, blank=True, null=True)
    hora = models.CharField(max_length=20, blank=True, null=True)
    defeito = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(blank=True, null=True)
    campos_extras = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente.cliente_id} - {self.tipo} - {self.data}"


class LogXML(models.Model):
    tipo_operacao = models.CharField(max_length=30)
    cliente_id = models.CharField(max_length=100, blank=True, null=True)
    xml_recebido = models.TextField()
    xml_enviado = models.TextField()
    status_code = models.IntegerField()
    sucesso = models.BooleanField(default=True)
    mensagem_erro = models.TextField(blank=True, null=True)
    ip_address = models.CharField(max_length=100, blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo_operacao} - {self.cliente_id} - {self.timestamp}"