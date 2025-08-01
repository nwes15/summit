import xml.etree.ElementTree as ET
from django.views import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Cliente, Historico

def gerar_erro_xml(mensagem, short_text="Erro"):
    return HttpResponse(
        f'''<?xml version="1.0" encoding="utf-16"?>
<ResponseV2 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <MessageV2>
        <Text>{mensagem}</Text>
    </MessageV2>
    <ReturnValueV2>
        <Fields/>
        <ShortText>{short_text}</ShortText>
        <LongText/>
        <Value>0</Value>
    </ReturnValueV2>
</ResponseV2>
''',
        content_type="application/xml; charset=utf-16",
        status=400
    )

@method_decorator(csrf_exempt, name='dispatch')
class CreateHistoryViewXML(View):
    def post(self, request, *args, **kwargs):
        try:
            xml_data = request.body.decode('utf-8')
            root = ET.fromstring(xml_data)
            cliente_field = root.find(".//Field[Id='CLIENTE']")
            if cliente_field is None or cliente_field.find("Value") is None:
                return gerar_erro_xml("CLIENTE não encontrado no XML", "CLIENTE não encontrado")
            cliente_id = cliente_field.find("Value").text

            cliente, _ = Cliente.objects.get_or_create(cliente_id=cliente_id)

            table_field = root.find(".//TableField[Id='HISTORICO']")
            if table_field is None:
                return gerar_erro_xml("TableField HISTORICO não encontrado", "HISTORICO não encontrado")

            rows = table_field.find("Rows")
            if rows is None:
                return gerar_erro_xml("Nenhuma Row encontrada em HISTORICO", "Row não encontrada")

            historicos_salvos = 0
            for row in rows.findall("Row"):
                campos = {}
                fields = row.find("Fields")
                if fields is not None:
                    for field in fields.findall("Field"):
                        field_id_elem = field.find("Id")
                        field_value_elem = field.find("Value")
                        if field_id_elem is not None and field_value_elem is not None:
                            field_id = field_id_elem.text or ''
                            field_value = field_value_elem.text or ''
                            campos[field_id] = field_value

                tipo = campos.get('TIPO', '')
                data = campos.get('DATA', '')
                hora = campos.get('HORA', '')
                defeito = campos.get('DEFEITO', '')
                descricao = campos.get('DESCRICAO', '')

                campos_extras = {k: v for k, v in campos.items() if k not in ['TIPO', 'DATA', 'HORA', 'DEFEITO', 'DESCRICAO']}

                Historico.objects.create(
                    cliente=cliente,
                    tipo=tipo,
                    data=data,
                    hora=hora,
                    defeito=defeito,
                    descricao=descricao,
                    campos_extras=campos_extras
                )
                historicos_salvos += 1

            return HttpResponse(
                f'''<?xml version="1.0" encoding="utf-16"?>
<ResponseV2 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <MessageV2>
        <Text>Histórico(s) cadastrado(s) com sucesso</Text>
    </MessageV2>
    <ReturnValueV2>
        <Fields/>
        <ShortText>Sucesso</ShortText>
        <LongText/>
        <Value>{historicos_salvos}</Value>
    </ReturnValueV2>
</ResponseV2>
''',
                content_type="application/xml; charset=utf-16",
                status=200
            )

        except ET.ParseError as e:
            return gerar_erro_xml(f"Erro ao processar XML: {str(e)}", "XML inválido")
        except Exception as e:
            return gerar_erro_xml(str(e), "Erro interno")

class ItemListViewXML(View):
    def get(self, request, *args, **kwargs):
        cliente_id = request.GET.get('cliente_id')
        if not cliente_id:
            return gerar_erro_xml("Parâmetro cliente_id é obrigatório", "cliente_id obrigatório")
        try:
            cliente = Cliente.objects.get(cliente_id=cliente_id)
            historicos = cliente.historicos.all().order_by('-created_at')
            if not historicos.exists():
                return gerar_erro_xml("Nenhum histórico encontrado para este cliente", "Sem histórico")

            rows_xml = ""
            for historico in historicos:
                fields_xml = ""
                campos_principais = {
                    'TIPO': historico.tipo,
                    'DATA': historico.data,
                    'HORA': historico.hora,
                    'DEFEITO': historico.defeito,
                    'DESCRICAO': historico.descricao
                }
                for field_id, field_value in campos_principais.items():
                    if field_value:
                        fields_xml += f"""
                            <Field>
                                <ID>{field_id}</ID>
                                <Value>{field_value}</Value>
                            </Field>"""
                for field_id, field_value in historico.campos_extras.items():
                    if field_value:
                        fields_xml += f"""
                            <Field>
                                <ID>{field_id}</ID>
                                <Value>{field_value}</Value>
                            </Field>"""
                rows_xml += f"""
                    <Row>
                        <Fields>{fields_xml}
                        </Fields>
                    </Row>"""

            response_xml = f"""<?xml version="1.0" encoding="utf-16"?>
<ResponseV2 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <MessageV2>
        <Text>Consulta realizada com sucesso</Text>
    </MessageV2>
    <ReturnValueV2>
        <Fields>
            <TableField>
                <ID>HISTORICO</ID>
                <Rows>{rows_xml}
                </Rows>
            </TableField>
        </Fields>
        <ShortText>Histórico do cliente</ShortText>
        <LongText/>
        <Value>1</Value>
    </ReturnValueV2>
</ResponseV2>"""

            return HttpResponse(response_xml, content_type='application/xml; charset=utf-16')

        except Cliente.DoesNotExist:
            return gerar_erro_xml("Cliente não encontrado", "Cliente não encontrado")
        except Exception as e:
            return gerar_erro_xml(str(e), "Erro interno")