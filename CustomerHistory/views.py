import logging
from datetime import datetime
from lxml import etree
import xml.etree.ElementTree as ET

from django.views import View
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Cliente, Historico, LogXML  # Inclua LogXML se estiver usando logs
from django.utils import timezone

logger = logging.getLogger(__name__)


def formatar_data_e_hora(datahora_str):
    """
    Separa e converte 'ddmmyyyyHHMM' em ('dd/mm/yyyy', 'HH:MM').
    Exemplo: '060820251416' → ('06/08/2025', '14:16')
    """
    try:
        data_part = datahora_str[:8]
        hora_part = datahora_str[8:]

        data_obj = datetime.strptime(data_part, '%d%m%Y')
        data_formatada = data_obj.strftime('%d/%m/%Y')

        hora_obj = datetime.strptime(hora_part, '%H%M')
        hora_formatada = hora_obj.strftime('%H:%M')

        return data_formatada, hora_formatada
    except Exception:
        return datahora_str, ''


def extrair_xml_request(request):
    xml_data = None
    if request.method == "POST":
        DEFAULT_CAMPOS = ["TextXML", "textxml", "xmldata", "xml", "application/x-www-form-urlencoded"]
        for campo in DEFAULT_CAMPOS:
            if campo in request.POST:
                xml_data = request.POST.get(campo)
                break
        if not xml_data and len(request.POST) > 0:
            primeiro = list(request.POST.keys())[0]
            xml_data = request.POST.get(primeiro)
    if not xml_data and request.body:
        raw = request.body
        try:
            xml_data = raw.decode('utf-8')
        except Exception:
            xml_data = raw.decode("utf-8", errors='ignore')
    return xml_data


def escape_xml_content(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gerar_erro_xml(mensagem, short_text="Erro"):
    response_xml = f'''<?xml version="1.0" encoding="utf-16"?>
<ResponseV2 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <MessageV2>
        <Text>{escape_xml_content(mensagem)}</Text>
    </MessageV2>
    <ReturnValueV2>
        <Fields/>
        <ShortText>{escape_xml_content(short_text)}</ShortText>
        <LongText/>
        <Value>0</Value>
    </ReturnValueV2>
</ResponseV2>'''
    return HttpResponse(
        response_xml.encode('utf-16'),
        content_type='application/xml; charset=utf-16',
        status=400
    )


def adicionar_field(parent, field_id, value):
    field = etree.SubElement(parent, "Field")
    etree.SubElement(field, "ID").text = str(field_id)
    etree.SubElement(field, "Value").text = str(value) if value is not None else ""


def montar_xml_dinamico(historicos):
    nsmap = {'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
             'xsd': 'http://www.w3.org/2001/XMLSchema'}
    response = etree.Element("ResponseV2", nsmap=nsmap)
    message = etree.SubElement(response, "MessageV2")
    etree.SubElement(message, "Text").text = "Consulta realizada com sucesso"
    return_value = etree.SubElement(response, "ReturnValueV2")
    fields = etree.SubElement(return_value, "Fields")
    table_field = etree.SubElement(fields, "TableField")
    etree.SubElement(table_field, "ID").text = "HISTORICO"
    rows = etree.SubElement(table_field, "Rows")

    for historico in historicos:
        row = etree.SubElement(rows, "Row")
        row_fields = etree.SubElement(row, "Fields")
        adicionar_field(row_fields, "TIPO", historico.tipo)
        data_br, hora_br = formatar_data_e_hora(historico.data)
        adicionar_field(row_fields, "DATA", data_br)
        adicionar_field(row_fields, "HORA", hora_br)
        adicionar_field(row_fields, "DEFEITO", historico.defeito)
        adicionar_field(row_fields, "DESCRICAO", historico.descricao)
        if hasattr(historico, "campos_extras") and isinstance(historico.campos_extras, dict):
            for k, v in historico.campos_extras.items():
                if v:
                    adicionar_field(row_fields, k, v)

    etree.SubElement(return_value, "ShortText").text = "Histórico do cliente"
    etree.SubElement(return_value, "LongText")
    etree.SubElement(return_value, "Value").text = str(len(historicos))

    xml_declaration = '<?xml version="1.0" encoding="utf-16"?>'
    xml_bytes = etree.tostring(response, encoding="utf-16", xml_declaration=False)
    xml_str = xml_declaration + "\n" + xml_bytes.decode("utf-16")
    return xml_str


def salvar_log_xml(tipo_operacao, cliente_id, xml_recebido, xml_enviado, status_code,
                   request, sucesso=True, mensagem_erro=None):
    try:
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        LogXML.objects.create(
            tipo_operacao=tipo_operacao,
            cliente_id=cliente_id,
            xml_recebido=xml_recebido,
            xml_enviado=xml_enviado,
            status_code=status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            sucesso=sucesso,
            mensagem_erro=mensagem_erro,
        )
    except Exception as e:
        logger.error(f"Erro ao salvar log: {e}")


@method_decorator(csrf_exempt, name='dispatch')
class CreateHistoryViewXML(View):
    def post(self, request, *args, **kwargs):
        try:
            logger.info("=== CADASTRO DE HISTÓRICO INICIADO ===")
            xml_data = extrair_xml_request(request)
            logger.info(f"XML recebido (500 chars): {xml_data[:500] if xml_data else '[VAZIO]'}")

            if not xml_data or not xml_data.strip():
                logger.error("XML vazio recebido")
                return HttpResponse("_OK_", content_type="text/plain", status=200)

            try:
                root = ET.fromstring(xml_data)
                logger.info(f"XML parseado com sucesso. Tag raiz: {root.tag}")
            except ET.ParseError as parse_error:
                logger.error(f"Erro ao fazer parse do XML: {parse_error}")
                return HttpResponse("_OK_", content_type="text/plain", status=200)

            cliente_field = root.find(".//Field[Id='CLIENTE']")
            if cliente_field is None:
                logger.error("Campo CLIENTE não encontrado no XML")
                return HttpResponse("_OK_", content_type="text/plain", status=200)
            cliente_value_elem = cliente_field.find("Value")
            if cliente_value_elem is None or not cliente_value_elem.text:
                logger.error("Valor do CLIENTE vazio ou não encontrado")
                return HttpResponse("_OK_", content_type="text/plain", status=200)
            cliente_id = cliente_value_elem.text.strip()
            logger.info(f"Cliente ID extraído: '{cliente_id}'")

            try:
                cliente, cliente_criado = Cliente.objects.get_or_create(cliente_id=cliente_id)
                if cliente_criado:
                    logger.info(f"NOVO cliente criado: {cliente_id}")
                else:
                    logger.info(f"Cliente existente encontrado: {cliente_id}")
            except Exception as cliente_error:
                logger.error(f"Erro ao processar cliente: {cliente_error}")
                return HttpResponse("_OK_", content_type="text/plain", status=200)

            fields_elem = root.find(".//Fields")
            if fields_elem is None:
                logger.error("Fields não encontrado no XML")
                return HttpResponse("_OK_", content_type="text/plain", status=200)

            campos = {}
            for field in fields_elem.findall("Field"):
                id_elem = field.find("Id")
                value_elem = field.find("Value")
                if id_elem is not None and value_elem is not None:
                    field_id = id_elem.text or ''
                    field_value = value_elem.text or ''
                    campos[field_id] = field_value

            historico = Historico.objects.create(
                cliente=cliente,
                tipo=campos.get('TIPO', '') or campos.get('TIPO_S', ''),
                data=campos.get('DATA', '') or campos.get('DATA_S', ''),
                hora=campos.get('HORA', '') or campos.get('HORA_S', ''),
                defeito=campos.get('DEFEITO', '') or campos.get('DEFEITO_S', ''),
                descricao=campos.get('DESCRICAO', '') or campos.get('DESCRICAO_S', ''),
                campos_extras={k: v for k, v in campos.items()
                               if k not in ['TIPO', 'TIPO_S', 'DATA', 'DATA_S', 'HORA',
                                            'HORA_S', 'DEFEITO', 'DEFEITO_S', 'DESCRICAO', 'DESCRICAO_S']}
            )
            logger.info(f"Histórico salvo com ID: {historico.id}")

            salvar_log_xml("CADASTRO", cliente_id, xml_data, "_OK_", 200, request, True)

            # Retorna texto simples _OK_
            return HttpResponse("_OK_", content_type='text/plain', status=200)

        except Exception as e:
            logger.error(f"ERRO GERAL: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Também retorna _OK_ mesmo em caso de erro, para evitar reenviamentos
            return HttpResponse("_OK_", content_type='text/plain', status=200)



@method_decorator(csrf_exempt, name='dispatch')
class ItemListViewXML(View):
    def post(self, request, *args, **kwargs):
        try:
            logger.info("=== CONSULTA DE HISTÓRICO INICIADA ===")
            xml_data = extrair_xml_request(request)
            logger.info(f"XML recebido (500 chars): {xml_data[:500] if xml_data else '[VAZIO]'}")
            if not xml_data or not xml_data.strip():
                logger.error("XML vazio recebido")
                return gerar_erro_xml("XML vazio ou não fornecido", "XML vazio")
            try:
                root = ET.fromstring(xml_data)
            except ET.ParseError as parse_error:
                logger.error(f"Erro parse XML consulta: {parse_error}")
                return gerar_erro_xml(f"XML inválido: {parse_error}", "Parse Error")
            cliente_field = root.find(".//Field[Id='CLIENTE']")
            if cliente_field is None:
                return gerar_erro_xml("Campo CLIENTE não encontrado na consulta", "CLIENTE obrigatório")
            cliente_value_elem = cliente_field.find("Value")
            if cliente_value_elem is None or not cliente_value_elem.text:
                return gerar_erro_xml("Valor do CLIENTE é obrigatório na consulta", "CLIENTE vazio")
            cliente_id = cliente_value_elem.text.strip()
            logger.info(f"Consultando histórico do cliente: '{cliente_id}'")
            try:
                cliente = Cliente.objects.get(cliente_id=cliente_id)
                logger.info(f"Cliente encontrado no banco: {cliente_id}")
            except Cliente.DoesNotExist:
                logger.warning(f"Cliente não existe: {cliente_id}")
                return gerar_erro_xml("Cliente não encontrado", "Cliente inexistente")
            historicos = cliente.historicos.all().order_by('-created_at')
            if not historicos:
                return gerar_erro_xml("Nenhum histórico encontrado para este cliente", "Sem histórico")
            xml_str = montar_xml_dinamico(historicos)
            salvar_log_xml("CONSULTA", cliente_id, xml_data, xml_str, 200, request, True)
            return HttpResponse(xml_str.encode('utf-16'), content_type='application/xml; charset=utf-16')
        except Exception as e:
            logger.error(f"ERRO GERAL na consulta: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return gerar_erro_xml(f"Erro interno: {str(e)}", "Erro do servidor")
