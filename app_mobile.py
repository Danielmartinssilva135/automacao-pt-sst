import os
import re
from datetime import datetime
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas

from src.emissor_pt import gerar_pdf_pt
from src.validador import descarregar_aba, validar_executante

st.set_page_config(
    page_title="SST Mobile - Liberação In Loco",
    page_icon="🛡️",
    layout="centered",
)

st.title("🛡️ SST Mobile - Liberação In Loco")
st.caption("Inspeção Presencial, Análise de Risco e Assinaturas Digitais")

# 1. Carrega dados do Google Sheets
try:
  df_solic = descarregar_aba("Solicitações PT")
  df_solic.columns = [c.strip().upper() for c in df_solic.columns]

  df_colab = descarregar_aba("Colaboradores")
  df_colab.columns = [c.strip().upper() for c in df_colab.columns]
  col_cpf_c = next((c for c in df_colab.columns if "CPF" in c), "CPF")
  col_nome_c = next((c for c in df_colab.columns if "NOME" in c), "NOME")
  col_cargo_c = next(
      (c for c in df_colab.columns if "FUNÇÃO" in c or "CARGO" in c), None
  )
except Exception as e:
  st.error(f"Erro ao carregar dados do Google Sheets: {e}")
  st.stop()

# Filtra apenas o que veio do pré-cadastro do solicitante
col_status = next((c for c in df_solic.columns if "STATUS" in c), "STATUS")
pendentes = df_solic[
    df_solic[col_status]
    .astype(str)
    .str.strip()
    .str.upper()
    .isin(["PENDENTE", "AGUARDANDO_INSPECAO"])
]

if pendentes.empty:
  st.success("✅ Nenhuma solicitação pendente de vistoria no momento!")
  st.stop()

# 2. Seleção da PT
opcoes_pt = [
    f"PT {row.get('ID SOLICITACAO', idx)} - {row.get('LOCAL', 'Sem Local')}"
    for idx, row in pendentes.iterrows()
]
escolha = st.selectbox("Selecione a PT para vistoria:", opcoes_pt)
idx_selecionado = opcoes_pt.index(escolha)
pt_selecionada = pendentes.iloc[idx_selecionado]

numero_pt = str(pt_selecionada.get("ID SOLICITACAO", "1002")).strip()
solicitante = str(pt_selecionada.get("SOLICITANTE", "Não informado")).strip()
local = str(pt_selecionada.get("LOCAL", "Frente de Obra")).strip()
atividade = str(
    pt_selecionada.get("ATIVIDADE", "Atividade Operacional")
).strip()

st.info(f"""
**Dados do Pré-Cadastro (Solicitante):**
* **Local:** {local}
* **Atividade:** {atividade}
* **Solicitante:** {solicitante}
""")

st.divider()

# 3. Identificação do Emitente In Loco
st.subheader("1. Identificação do Emitente / Liberador")
emitente_nome = st.text_input(
    "Nome do Responsável pela Liberação:", placeholder="Ex: Técnico de SST"
)

# 4. Análise de Risco In Loco
st.subheader("2. Análise de Risco In Loco (Avaliação Presencial)")
st.write(
    "Avalie e confirme os riscos reais observados diretamente no ambiente:"
)

col_r1, col_r2 = st.columns(2)
with col_r1:
  risco_altura = st.checkbox("Trabalho em Altura (NR-35)", value=True)
  risco_eletrica = st.checkbox("Instalações Elétricas (NR-10)")
with col_r2:
  risco_confinado = st.checkbox("Espaço Confinado (NR-33)")
  risco_quente = st.checkbox("Trabalho a Quente / Solda (NR-34)")

riscos_selecionados = []
if risco_altura:
  riscos_selecionados.append("NR-35")
if risco_eletrica:
  riscos_selecionados.append("NR-10")
if risco_confinado:
  riscos_selecionados.append("NR-33")
if risco_quente:
  riscos_selecionados.append("NR-34")

# 5. Registro Fotográfico Obrigatório
st.subheader("3. Registro Fotográfico Obrigatório do Local")
st.caption(
    "A foto deve ser capturada exclusivamente pela câmera para comprovar a"
    " vistoria in loco."
)
foto_camera = st.camera_input(
    "Capturar foto do ambiente / isolamento", key="cam_local_obrigatoria"
)

st.divider()

# 6. Gestão da Equipe de Executantes
st.subheader("4. Validação da Equipe e Assinaturas Digitais")

cpfs_previstos_raw = str(
    pt_selecionada.get(
        "CPFS EQUIPE",
        pt_selecionada.get("EQUIPE", pt_selecionada.get("CPF", "")),
    )
)
cpfs_iniciais = [
    c.strip()
    for c in cpfs_previstos_raw.replace(";", ",").split(",")
    if c.strip() and c.strip().lower() != "nan"
]

mapa_colaboradores = {}
info_base_colab = {}
for _, c_row in df_colab.iterrows():
  c_cpf = str(c_row[col_cpf_c]).strip()
  c_nome = str(c_row[col_nome_c]).strip()
  c_cargo = (
      str(c_row[col_cargo_c]).strip() if col_cargo_c else "Operacional"
  )
  label = f"{c_nome} ({c_cpf})"
  mapa_colaboradores[label] = c_cpf
  info_base_colab[c_cpf] = {"nome": c_nome, "funcao": c_cargo}

opcoes_colaboradores = list(mapa_colaboradores.keys())
padroes_selecionados = [
    k
    for k, v in mapa_colaboradores.items()
    if any(re.sub(r"\D", "", v) in re.sub(r"\D", "", cp) for cp in cpfs_iniciais)
]

colabs_selecionados = st.multiselect(
    "Equipe executante na frente de serviço (adicione ou ajuste os"
    " trabalhadores):",
    options=opcoes_colaboradores,
    default=padroes_selecionados,
)

dados_equipe_aprovada = []
bloqueios = []
faltam_assinaturas = []

if not colabs_selecionados:
  st.warning("Selecione pelo menos um trabalhador para a equipe de execução.")
else:
  for idx_c, item_label in enumerate(colabs_selecionados):
    cpf_alvo = mapa_colaboradores[item_label]
    dados_padrao = info_base_colab.get(
        cpf_alvo, {"nome": item_label, "funcao": "Operacional"}
    )

    apto, res_validacao = validar_executante(cpf_alvo, riscos_selecionados)

    # Compatibilidade: funciona se res_validacao for dict ou string
    if isinstance(res_validacao, dict):
      nome_func = res_validacao.get("nome", dados_padrao["nome"])
      funcao_func = res_validacao.get("funcao", dados_padrao["funcao"])
      motivo_func = res_validacao.get(
          "motivo", "Apto" if apto else "Não em conformidade"
      )
    else:
      nome_func = dados_padrao["nome"]
      funcao_func = dados_padrao["funcao"]
      motivo_func = str(res_validacao)

    with st.expander(f"👷 {nome_func} — {funcao_func}", expanded=True):
      if apto:
        st.success(f"✔️ Apto para os riscos: {', '.join(riscos_selecionados)}")

        # Selfie / Confirmação Facial
        st.write("📷 Selfie / Confirmação Facial do Trabalhador:")
        foto_executante = st.camera_input(
            f"Selfie de {nome_func}", key=f"face_{cpf_alvo}_{idx_c}"
        )

        caminho_face = None
        if foto_executante:
          os.makedirs("fotos_faciais", exist_ok=True)
          caminho_face = f"fotos_faciais/face_{cpf_alvo}_{idx_c}.jpg"
          with open(caminho_face, "wb") as f:
            f.write(foto_executante.getbuffer())

        # Rubrica Touchscreen
        st.write(f"✍️ Rubrica de **{nome_func}** no ecrã (Obrigatória):")
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#FFFFFF",
            update_streamlit=True,
            height=90,
            width=320,
            drawing_mode="freedraw",
            key=f"rubrica_{cpf_alvo}_{idx_c}",
        )

        caminho_rubrica = None
        tem_assinatura = False
        if canvas_result is not None and canvas_result.json_data is not None:
          objetos = canvas_result.json_data.get("objects", [])
          if len(objetos) > 0:
            tem_assinatura = True

        if tem_assinatura and canvas_result.image_data is not None:
          os.makedirs("assinaturas", exist_ok=True)
          caminho_rubrica = f"assinaturas/rubrica_{cpf_alvo}_{idx_c}.png"
          img_rubrica = Image.fromarray(
              canvas_result.image_data.astype("uint8")
          )
          img_rubrica.save(caminho_rubrica)
        else:
          faltam_assinaturas.append(nome_func)

        dados_equipe_aprovada.append({
            "nome": nome_func,
            "funcao": funcao_func,
            "rubrica": caminho_rubrica,
            "foto_facial": caminho_face,
        })
      else:
        st.error(f"❌ {motivo_func}")
        bloqueios.append(motivo_func)

st.divider()

# 7. Liberação Oficial da PT
if st.button("🚀 LIBERAR PERMISSÃO DE TRABALHO IN LOCO", type="primary"):
  if not emitente_nome:
    st.warning("⚠️ Preencha o nome do emitente responsável pela vistoria!")
  elif not foto_camera:
    st.warning(
        "⚠️ É obrigatório registrar a foto da frente de serviço pela câmera!"
    )
  elif not dados_equipe_aprovada:
    st.warning("⚠️ Nenhum colaborador selecionado para a atividade!")
  elif bloqueios:
    st.error(
        "A PT não pode ser liberada devido a pendências na qualificação da"
        " equipe!"
    )
  elif faltam_assinaturas:
    nomes_pendentes = ", ".join(faltam_assinaturas)
    st.error(
        f"⛔ BLOQUEIO: Todos os executantes devem assinar no ecrã! Falta a"
        f" assinatura de: {nomes_pendentes}."
    )
  else:
    os.makedirs("fotos_locais", exist_ok=True)
    caminho_foto = f"fotos_locais/foto_{numero_pt}.jpg"
    with open(caminho_foto, "wb") as f:
      f.write(foto_camera.getbuffer())

    hora_agora = datetime.now().strftime("%H:%M:%S")
    nome_pdf = f"PT_{numero_pt}.pdf"

    gerar_pdf_pt(
        numero_pt=numero_pt,
        atividade=atividade,
        local=local,
        solicitante=solicitante,
        emitente_in_loco=emitente_nome,
        equipe=dados_equipe_aprovada,
        riscos=riscos_selecionados,
        foto_local=caminho_foto,
        hora_in_loco=hora_agora,
        nome_arquivo=nome_pdf,
    )

    st.success(f"🎉 PT N.º {numero_pt} LIBERADA COM SUCESSO IN LOCO!")

    with open(nome_pdf, "rb") as pdf_file:
      st.download_button(
          label="📥 Descarregar PT Emitida (PDF)",
          data=pdf_file,
          file_name=nome_pdf,
          mime="application/pdf",
      )
