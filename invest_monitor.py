import yfinance as yf
import pandas as pd
import io
import os
import requests
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

def enviar_telegram(mensagem):
    # Lendo das variáveis de ambiente do GitHub
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def rebalancear():
    # 1. Sua Carteira Real
    carteira = {
        "MELI34.SA": {"alvo_pct": 0.100, "quantidade": 140},
        "CPTS11.SA": {"alvo_pct": 0.198, "quantidade": 2500},
        "ITUB4.SA":  {"alvo_pct": 0.148, "quantidade": 350},
        "FIIB11.SA": {"alvo_pct": 0.051, "quantidade": 11},
        "KNCR11.SA": {"alvo_pct": 0.021, "quantidade": 20},
        "TOTS3.SA":  {"alvo_pct": 0.102, "quantidade": 300},
        "HGLG11.SA": {"alvo_pct": 0.153, "quantidade": 100},
        "XPML11.SA": {"alvo_pct": 0.104, "quantidade": 100},
        "EGIE3.SA":  {"alvo_pct": 0.123, "quantidade": 400}
    }

    print("Buscando cotações...")
    dados_carteira = []
    valor_total_atual = 0

    for ticker, info in carteira.items():
        acao = yf.Ticker(ticker)
        preco = acao.history(period="1d")['Close'].iloc[0]
        valor_posicao = preco * info["quantidade"]
        valor_total_atual += valor_posicao
        dados_carteira.append({
            "Ativo": ticker.replace(".SA", ""),
            "Alvo (%)": info["alvo_pct"] * 100,
            "Quantidade": info["quantidade"],
            "Preço Atual": round(preco, 2),
            "Valor Atual": round(valor_posicao, 2)
        })

    df = pd.DataFrame(dados_carteira)
    df["Atual (%)"] = round((df["Valor Atual"] / valor_total_atual) * 100, 2)
    df["Distância (%)"] = round(df["Alvo (%)"] - df["Atual (%)"], 2)
    ativo_comprar = df.loc[df["Distância (%)"].idxmax()]

    # 2. Autenticação Automática no Google Drive
    # O conteúdo do JSON da Service Account virá de um segredo do GitHub
    try:
        service_account_info = json.loads(os.getenv('GOOGLE_DRIVE_CREDENTIALS'))
        creds = service_account.Credentials.from_service_account_info(service_account_info)
        drive_service = build('drive', 'v3', credentials=creds)
        file_id = '1LbmYsweetz62wP4J_g4vFMVcqnPDrH2z'

        # Download do histórico
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        fh.seek(0)
        
        df_hist = pd.read_csv(fh)
        df_nova = df.copy()
        df_nova.insert(0, 'Data', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        df_nova['Total Carteira'] = round(valor_total_atual, 2)
        df_nova['Recomendação'] = ativo_comprar['Ativo']
        
        df_final = pd.concat([df_hist, df_nova], ignore_index=True)
        df_final.to_csv('temp.csv', index=False)
        
        media = MediaFileUpload('temp.csv', mimetype='text/csv')
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        status_drive = "✅ Histórico atualizado no Drive."
    except Exception as e:
        status_drive = f"❌ Erro no Drive: {str(e)}"

    # 3. Relatório para o Telegram
    total_fmt = f"R$ {valor_total_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    msg = (f"🤖 *Monitor Diário de Investimentos*\n\n"
           f"📊 *Total:* {total_fmt}\n"
           f"🎯 *Melhor Compra:* {ativo_comprar['Ativo']}\n"
           f"📈 *Distância do Alvo:* {ativo_comprar['Distância (%)']}%\n\n"
           f"{status_drive}")
    
    enviar_telegram(msg)

if __name__ == "__main__":
    rebalancear()
