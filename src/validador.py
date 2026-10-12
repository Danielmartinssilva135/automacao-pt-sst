import io
import urllib.parse
from datetime import datetime
import pandas as pd
import requests

SHEET_ID = "1XJToLN8NuFAltauroxziS0lkqgBkok292gxEKKofzV4"

def descarregar_aba(nome_aba: str) -> pd.DataFrame:
    aba_encoded = urllib.parse.quote(nome_aba)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={aba_encoded}"
    resposta = requests.get(url)
    if resposta.status_code != 200:
        raise ConnectionError(f"Erro ao acessar aba '{nome_aba}'. Verifique o acesso da planilha.")
    
    df = pd.read_csv(io.StringIO(resposta.text))
    col_cpf = [c for c in df.columns if "CPF" in c.upper()]
    if col_cpf:
        df.rename(columns={col_cpf[0]: "CPF"}, inplace=True)
        df["CPF"] = df["CPF"].astype(str).str.strip()
    return df

def validar_executante(cpf: str, riscos: list[str]) -> tuple[bool, str]:
    colabs = descarregar_aba("Colaboradores")
    asos = descarregar_aba("Saúde ocupacional")
    treinos = descarregar_aba("Treinamento NR")
    
    hoje = pd.to_datetime(datetime.now().date())
    
    c = colabs[colabs["CPF"] == cpf]
    if c.empty:
        return False, f"CPF {cpf}: Colaborador não cadastrado."
    
    nome = c.iloc[0].get("Nome Completo", f"CPF {cpf}")
    
    if str(c.iloc[0].get("Ativo", "")).strip().upper() != "SIM":
        return False, f"{nome}: Cadastro inativo."
        
    aso = asos[asos["CPF"] == cpf]
    if aso.empty:
        return False, f"{nome}: Sem ASO registrado."
        
    col_venc_aso = [col for col in aso.columns if "VENCIMENTO" in col.upper()]
    if col_venc_aso:
        venc_aso = pd.to_datetime(aso.iloc[0][col_venc_aso[0]], dayfirst=True)
        if venc_aso < hoje:
            return False, f"{nome}: ASO vencido em {venc_aso.strftime('%d/%m/%Y')}."

    erros = []
    for risco in riscos:
        t = treinos[(treinos["CPF"] == cpf) & (treinos["Norma / Treinamento"].str.contains(risco, case=False, na=False))]
        if t.empty:
            erros.append(f"sem curso de {risco}")
        else:
            col_venc_t = [col for col in t.columns if "VALIDADE" in col.upper()]
            if col_venc_t:
                venc_t = pd.to_datetime(t.iloc[0][col_venc_t[0]], dayfirst=True)
                if venc_t < hoje:
                    erros.append(f"{risco} vencida em {venc_t.strftime('%d/%m/%Y')}")
                    
    if erros:
        return False, f"{nome}: Pendência ({', '.join(erros)})."
        
    return True, f"{nome}: Apto para atividade."
