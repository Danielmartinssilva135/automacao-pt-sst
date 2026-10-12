from datetime import datetime, timedelta
import io
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def gerar_pdf_pt(numero_pt: str, atividade: str, local: str, equipe: list[str], validade_horas: int = 8, nome_arquivo: str = None) -> str:
    if not nome_arquivo:
        nome_arquivo = f"PT_{numero_pt}.pdf"

    inicio = datetime.now()
    fim = inicio + timedelta(hours=validade_horas)

    c = canvas.Canvas(nome_arquivo, pagesize=letter)
    largura, altura = letter

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, altura - 50, "PERMISSÃO DE TRABALHO (PT) - SST")
    c.setFont("Helvetica", 10)
    c.drawString(50, altura - 70, f"Documento de Liberação Operacional - N.º {numero_pt}")

    c.line(50, altura - 78, largura - 50, altura - 78)

    # Dados da Atividade
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, altura - 105, "1. INFORMAÇÕES DA ATIVIDADE")
    c.setFont("Helvetica", 10)
    c.drawString(60, altura - 125, f"Atividade: {atividade}")
    c.drawString(60, altura - 142, f"Local / Setor: {local}")
    c.drawString(60, altura - 159, f"Emissão: {inicio.strftime('%d/%m/%Y %H:%M')}")
    c.drawString(60, altura - 176, f"Validade até: {fim.strftime('%d/%m/%Y %H:%M')} ({validade_horas}h)")

    # Executantes Aprovados
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, altura - 210, "2. EXECUTANTES APTOS (ASO E NRs VALIDADOS)")
    c.setFont("Helvetica", 10)
    y = altura - 230
    for membro in equipe:
        c.drawString(60, y, f"• {membro}")
        y -= 18

    # Campo de Assinatura e QR Code de Validação
    c.line(50, y - 20, largura - 50, y - 20)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y - 40, "3. AUTORIZAÇÃO E RASTREABILIDADE")
    c.setFont("Helvetica", 9)
    c.drawString(50, y - 60, "Assinado digitalmente pelo Setor de Segurança do Trabalho.")
    c.drawString(50, y - 75, "Consulte a autenticidade apontando a câmara para o QR Code:")

    # Criação e desenho do QR Code
    dados_qr = f"PT:{numero_pt}|LOCAL:{local}|VALIDADE:{fim.strftime('%d/%m/%Y %H:%M')}|STATUS:APROVADA"
    qr = qrcode.make(dados_qr)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    c.drawInlineImage(qr_buffer, 50, y - 190, width=105, height=105)

    c.save()
    return nome_arquivo
