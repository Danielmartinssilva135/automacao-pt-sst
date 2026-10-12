from src.validador import validar_executante
from src.emissor_pt import gerar_pdf_pt

def processar_solicitacao_pt(numero_pt: str, atividade: str, local: str, riscos: list[str], cpfs_executantes: list[str]):
    print(f"--- PROCESSANDO SOLICITAÇÃO DE PT N.º {numero_pt} ---")
    print(f"Atividade: {atividade} | Local: {local}")
    print(f"Riscos / NRs envolvidas: {', '.join(riscos)}\n")

    aptos = []
    bloqueios = []

    # 1. Validação automática de cada trabalhador
    for cpf in cpfs_executantes:
        status_ok, mensagem = validar_executante(cpf, riscos)
        if status_ok:
            aptos.append(mensagem.replace(": Apto para atividade.", ""))
            print(f"  [APROVADO] {mensagem}")
        else:
            bloqueios.append(mensagem)
            print(f"  [BLOQUEADO] {mensagem}")

    # 2. Decisão de liberação
    if bloqueios:
        print("\n❌ EMISSÃO BLOQUEADA!")
        print("Motivos do impedimento:")
        for motivo in bloqueios:
            print(f"  - {motivo}")
        return None

    # 3. Geração da PT formal com QR Code
    print("\n✅ Toda a equipa cumpre os requisitos de ASO e NRs!")
    nome_pdf = gerar_pdf_pt(
        numero_pt=numero_pt,
        atividade=atividade,
        local=local,
        equipe=aptos,
        validade_horas=8
    )
    print(f"📄 PT gerada com sucesso: {nome_pdf}")
    return nome_pdf

if __name__ == "__main__":
    # Exemplo de teste prático:
    # Substitua pelos CPFs reais registados na sua Google Planilha
    cpfs_teste = ["111.222.333-44", "222.333.444-55"]
    riscos_teste = ["NR-35", "NR-10"]

    processar_solicitacao_pt(
        numero_pt="1001",
        atividade="Manutenção elétrica em iluminação de telhado",
        local="Galpão Principal - Setor B",
        riscos=riscos_teste,
        cpfs_executantes=cpfs_teste
    )
