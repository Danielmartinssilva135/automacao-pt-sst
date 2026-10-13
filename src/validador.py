import os
import re
from datetime import datetime
import pandas as pd
import requests

SHEET_ID = "1XJToLN8NuFAltauroxziS0lkqgBkok292gxEKKofzV4"


def limpar_cpf(cpf: str) -> str:
  if not cpf:
    return ""
  return re.sub(r"\D", "", str(cpf))


def converter_data(valor):
  if pd.isna(valor) or str(valor).strip() in ("", "nan", "None"):
    return None
  try:
    return pd.to_datetime(valor, dayfirst=True).to_pydatetime()
  except Exception:
    try:
      return pd.to_datetime(valor).to_pydatetime()
    except Exception:
      return None


def descarregar_aba(nome_aba: str) -> pd.DataFrame:
  url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(nome_aba)}"
  return pd.read_csv(url)


def validar_executante(
    cpf_busca: str, riscos_obrigatorios: list[str]
) -> tuple[bool, dict]:
  cpf_limpo = limpar_cpf(cpf_busca)
  hoje = datetime.now()

  df_colab = descarregar_aba("Colaboradores")
  df_aso = descarregar_aba("Saúde ocupacional")
  df_treina = descarregar_aba("Treinamento NR")

  df_colab.columns = [c.strip().upper() for c in df_colab.columns]
  df_aso.columns = [c.strip().upper() for c in df_aso.columns]
  df_treina.columns = [c.strip().upper() for c in df_treina.columns]

  col_cpf_c = next((c for c in df_colab.columns if "CPF" in c), None)
  col_nome_c = next((c for c in df_colab.columns if "NOME" in c), None)
  col_cargo_c = next(
      (c for c in df_colab.columns if "FUNÇÃO" in c or "CARGO" in c), None
  )

  df_colab["CPF_LIMPO"] = df_colab[col_cpf_c].apply(limpar_cpf)
  colab = df_colab[df_colab["CPF_LIMPO"] == cpf_limpo]

  if colab.empty:
    return False, {
        "nome": "Não Localizado",
        "funcao": "N/A",
        "motivo": f"CPF {cpf_busca} não encontrado.",
    }

  nome = str(colab.iloc[0][col_nome_c]).strip()
  funcao = (
      str(colab.iloc[0][col_cargo_c]).strip() if col_cargo_c else "Operacional"
  )

  # Validação do ASO
  col_cpf_a = next((c for c in df_aso.columns if "CPF" in c), None)
  col_venc_a = next(
      (c for c in df_aso.columns if "VENCIMENTO" in c and "CPF" not in c), None
  )
  if not col_venc_a:
    col_venc_a = next(
        (c for c in df_aso.columns if "VALIDADE" in c and "CPF" not in c), None
    )

  df_aso["CPF_LIMPO"] = df_aso[col_cpf_a].apply(limpar_cpf)
  aso_reg = df_aso[df_aso["CPF_LIMPO"] == cpf_limpo]

  if aso_reg.empty:
    return (
        False,
        {"nome": nome, "funcao": funcao, "motivo": f"{nome}: Sem registo de ASO."},
    )

  data_aso = converter_data(aso_reg.iloc[0][col_venc_a])
  if not data_aso or data_aso < hoje:
    data_str = data_aso.strftime("%d/%m/%Y") if data_aso else "Data inválida"
    return False, {
        "nome": nome,
        "funcao": funcao,
        "motivo": f"{nome}: ASO vencido em {data_str}.",
    }

  # Validação dos Treinamentos / NRs
  col_cpf_t = next((c for c in df_treina.columns if "CPF" in c), None)
  col_nr_t = next(
      (
          c
          for c in df_treina.columns
          if ("CURSO" in c or "NR" in c or "TREIN" in c or "NORMA" in c)
          and "CPF" not in c
      ),
      None,
  )
  col_venc_t = next(
      (
          c
          for c in df_treina.columns
          if ("VENCIMENTO" in c or "VALIDADE" in c) and "CPF" not in c
      ),
      None,
  )

  df_treina["CPF_LIMPO"] = df_treina[col_cpf_t].apply(limpar_cpf)
  treinos_colab = df_treina[df_treina["CPF_LIMPO"] == cpf_limpo]

  for risco in riscos_obrigatorios:
    padrao_nr = risco.replace("-", "").replace(" ", "").upper()
    treino_esp = treinos_colab[
        treinos_colab[col_nr_t]
        .astype(str)
        .str.replace("-", "")
        .str.replace(" ", "")
        .str.upper()
        .str.contains(padrao_nr)
    ]
    if treino_esp.empty:
      return False, {
          "nome": nome,
          "funcao": funcao,
          "motivo": f"{nome}: Falta formação {risco}.",
      }

    data_t = converter_data(treino_esp.iloc[0][col_venc_t])
    if not data_t or data_t < hoje:
      data_str = data_t.strftime("%d/%m/%Y") if data_t else "Data inválida"
      return False, {
          "nome": nome,
          "funcao": funcao,
          "motivo": f"{nome}: Curso {risco} vencido em {data_str}.",
      }

  return True, {
      "nome": nome,
      "funcao": funcao,
      "motivo": "Apto para a atividade.",
  }
