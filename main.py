
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright
from datetime import datetime
from pydantic import BaseModel, validator, root_validator
from typing import Optional
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

app = FastAPI(title="Robô Airbnb - Google Sheets Integration")

# Libera CORS para Manychat
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UNIDADES = [
    {
        "nome": "Eco Resort Praia Dos Carneiros - Flat Colina",
        "id": "614621079133481740",
        "chave": "flat_colina"
    },
    {
        "nome": "Eco Resort Praia Dos Carneiros - Flat Praia",
        "id": "1077091916761243151",
        "chave": "flat_praia"
    }
]

# ID da planilha Google Sheets
SPREADSHEET_ID = "1JG6srGE3WRt2OBzeHCUntW3KOGpzLTTVM83mbw1MEXU"

class ManychatRequest(BaseModel):
    # Dados do usuário
    nome: Optional[str] = None
    email: Optional[str] = None
    numero_whats: Optional[str] = None
    id_do_contato: str  # ID do WhatsApp (obrigatório)
    
    # Datas (aceita tanto Dchekin quanto Dcheckin)
    Dchekin: Optional[str] = None
    Dcheckin: Optional[str] = None
    Dcheckout: str
    
    # Número de hóspedes
    numero_hospede_numero: int
    
    @root_validator(pre=True)
    def normalizar_checkin(cls, values):
        """
        Aceita tanto Dchekin quanto Dcheckin e normaliza para Dcheckin
        """
        dchekin = values.get('Dchekin')
        dcheckin = values.get('Dcheckin')
        
        # Se Dchekin foi fornecido, usa ele
        if dchekin and not dcheckin:
            values['Dcheckin'] = dchekin
        # Se nenhum foi fornecido, erro
        elif not dchekin and not dcheckin:
            raise ValueError('É necessário fornecer Dchekin ou Dcheckin')
        
        return values
    
    @validator('numero_hospede_numero')
    def validar_hospedes(cls, v):
        if v < 1:
            raise ValueError('Deve haver pelo menos 1 hóspede')
        if v > 20:
            raise ValueError('Número máximo de hóspedes é 20')
        return v
    
    @validator('Dcheckin', 'Dcheckout')
    def validar_formato_data(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%d/%m/%Y")
            return v
        except ValueError:
            raise ValueError(f'Data inválida: {v}. Use o formato DD/MM/AAAA')

def conectar_google_sheets():
    """
    Conecta ao Google Sheets usando credenciais de service account
    """
    try:
        # Lê as credenciais da variável de ambiente
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_json:
            raise Exception("GOOGLE_CREDENTIALS não configurada")
        
        creds_dict = json.loads(creds_json)
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        return client
    except Exception as e:
        print(f"❌ Erro ao conectar Google Sheets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao conectar Google Sheets: {str(e)}")

def encontrar_linha_planilha(sheet, id_contato, checkin, checkout):
    """
    Encontra a linha na planilha baseado no ID do contato e datas
    """
    try:
        # Pega todos os valores da planilha
        all_values = sheet.get_all_values()
        
        # Cabeçalho está na linha 1 (índice 0)
        # Dados começam na linha 2 (índice 1)
        
        print(f"🔍 Procurando linha para: ID={id_contato}, Checkin={checkin}, Checkout={checkout}")
        
        for idx, row in enumerate(all_values[1:], start=2):  # Começa da linha 2
            # Coluna D (índice 3) = ID do Contato
            # Coluna E (índice 4) = checkin
            # Coluna F (índice 5) = checkout
            
            if len(row) > 5:
                row_id = row[3].strip() if len(row) > 3 else ""
                row_checkin = row[4].strip() if len(row) > 4 else ""
                row_checkout = row[5].strip() if len(row) > 5 else ""
                
                print(f"  Linha {idx}: ID={row_id}, Checkin={row_checkin}, Checkout={row_checkout}")
                
                if (row_id == id_contato and 
                    row_checkin == checkin and 
                    row_checkout == checkout):
                    print(f"✅ Linha encontrada: {idx}")
                    return idx
        
        print(f"❌ Linha não encontrada para ID={id_contato}")
        return None
        
    except Exception as e:
        print(f"❌ Erro ao procurar linha: {str(e)}")
        return None

def atualizar_planilha(sheet, linha, resultado):
    """
    Atualiza a planilha com os resultados da consulta
    """
    try:
        # Coluna G (7) = disp_colina
        # Coluna H (8) = valor_colina
        # Coluna I (9) = disp_praia
        # Coluna J (10) = valor_praia
        # Coluna K (11) = Achou (número de noites)
        
        updates = []
        
        # Flat Colina
        disp_colina = "Sim" if resultado['flat_colina_disponivel'] == "sim" else "Não"
        valor_colina = resultado['flat_colina_preco'] if resultado['flat_colina_preco'] else ""
        
        # Flat Praia
        disp_praia = "Sim" if resultado['flat_praia_disponivel'] == "sim" else "Não"
        valor_praia = resultado['flat_praia_preco'] if resultado['flat_praia_preco'] else ""
        
        # Número de noites
        numero_noites = str(resultado['numero_noites'])
        
        print(f"📝 Atualizando linha {linha}:")
        print(f"  G (disp_colina): {disp_colina}")
        print(f"  H (valor_colina): {valor_colina}")
        print(f"  I (disp_praia): {disp_praia}")
        print(f"  J (valor_praia): {valor_praia}")
        print(f"  K (Achou): {numero_noites}")
        
        # Atualiza célula por célula
        sheet.update_cell(linha, 7, disp_colina)      # G
        sheet.update_cell(linha, 8, valor_colina)     # H
        sheet.update_cell(linha, 9, disp_praia)       # I
        sheet.update_cell(linha, 10, valor_praia)     # J
        sheet.update_cell(linha, 11, numero_noites)   # K
        
        print(f"✅ Planilha atualizada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar planilha: {str(e)}")
        return False

def converter_data_manychat(data_str: str) -> str:
    """
    Converte data de DD/MM/AAAA (Manychat) para AAAA-MM-DD (Airbnb)
    """
    data_obj = datetime.strptime(data_str, "%d/%m/%Y")
    return data_obj.strftime("%Y-%m-%d")

def processar_consulta(dcheckin: str, dcheckout: str, numero_hospedes: int):
    """
    Função principal que processa a consulta no Airbnb
    """
    try:
        # Converte datas de DD/MM/AAAA para AAAA-MM-DD
        checkin = converter_data_manychat(dcheckin)
        checkout = converter_data_manychat(dcheckout)
        
        # Valida se checkout é posterior ao checkin
        data_in = datetime.strptime(checkin, "%Y-%m-%d")
        data_out = datetime.strptime(checkout, "%Y-%m-%d")
        
        if data_out <= data_in:
            raise HTTPException(
                status_code=400, 
                detail="Data de checkout deve ser posterior à data de checkin"
            )
        
        numero_noites = (data_out - data_in).days
        hospedes = numero_hospedes
        adultos = hospedes
        criancas = 0
        
        # Inicializa resultado padrão
        resultado = {
            "flat_colina_disponivel": "nao",
            "flat_colina_preco": "",
            "flat_colina_url": "",
            "flat_praia_disponivel": "nao",
            "flat_praia_preco": "",
            "flat_praia_url": "",
            "numero_noites": numero_noites,
            "checkin": dcheckin,
            "checkout": dcheckout,
            "hospedes": hospedes
        }

        with sync_playwright() as p:
            for unidade in UNIDADES:
                try:
                    print(f"🔍 Verificando: {unidade['nome']} ({unidade['id']})")
                    
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    
                    def handle_route(route):
                        url = route.request.url
                        if any(domain in url for domain in [
                            'a0.muscache.com',
                            'www.googletagmanager.com',
                            'google-analytics.com',
                            'facebook.com',
                            'doubleclick.net',
                            'googlesyndication.com',
                            'googleadservices.com',
                            'googletag',
                            'analytics.js',
                            'gtag',
                            'fbevents.js'
                        ]):
                            route.abort()
                        else:
                            route.continue_()
                    
                    context.route("**/*", handle_route)
                    page = context.new_page()
                    
                    url = (
                        f"https://www.airbnb.com.br/book/stays/{unidade['id']}"
                        f"?checkin={checkin}"
                        f"&checkout={checkout}"
                        f"&numberOfGuests={hospedes}"
                        f"&numberOfAdults={adultos}"
                        f"&numberOfChildren={criancas}"
                        f"&guestCurrency=BRL"
                        f"&productId={unidade['id']}"
                        f"&isWorkTrip=false"
                        f"&numberOfInfants=0&numberOfPets=0"
                    )
                    
                    print(f"🌐 URL acessada: {url}")
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(5000)

                    content = page.content()
                    
                    indisponivel_patterns = [
                        "não está disponível",
                        "não disponível",
                        "not available",
                        "já está reservada",
                        "already booked"
                    ]
                    
                    esta_indisponivel = any(pattern.lower() in content.lower() for pattern in indisponivel_patterns)
                    
                    match = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', content)
                    
                    if match and not esta_indisponivel:
                        preco_texto = match.group()
                        preco_limpo = preco_texto.replace("R$", "").replace(".", "").replace(",", ".").strip()
                        preco_total = float(preco_limpo)
                        preco_formatado = f"R$ {preco_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        print(f"✅ Disponível - Preço: {preco_formatado}")
                        
                        if unidade['chave'] == 'flat_colina':
                            resultado['flat_colina_disponivel'] = "sim"
                            resultado['flat_colina_preco'] = preco_formatado
                            resultado['flat_colina_url'] = url
                        elif unidade['chave'] == 'flat_praia':
                            resultado['flat_praia_disponivel'] = "sim"
                            resultado['flat_praia_preco'] = preco_formatado
                            resultado['flat_praia_url'] = url
                    else:
                        print(f"❌ Indisponível ou sem preço")
                    
                    browser.close()
                    print(f"🔄 Navegador fechado para {unidade['nome']}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao consultar {unidade['nome']}: {str(e)}")
                    browser.close()
                    continue

        print("🔚 Consulta finalizada.")
        return resultado

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar consulta: {str(e)}")

@app.get("/")
def root():
    return {
        "status": "online",
        "servico": "Robô Airbnb - Google Sheets Integration",
        "versao": "4.0",
        "nota": "Integrado com Google Sheets",
        "endpoints": {
            "consultar_post": "POST / ou POST /consultar (JSON body)",
            "health": "GET /health"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/")
@app.post("/consultar")
def consultar(request: ManychatRequest):
    """
    Endpoint para consulta via Manychat com integração Google Sheets
    
    Recebe:
    - nome: Nome do usuário
    - email: Email do usuário
    - numero_whats: Número do WhatsApp
    - id_do_contato: ID do contato no WhatsApp (obrigatório)
    - Dchekin OU Dcheckin: Data de check-in no formato DD/MM/AAAA
    - Dcheckout: Data de check-out no formato DD/MM/AAAA
    - numero_hospede_numero: Número de hóspedes
    
    Atualiza a planilha Google Sheets com os resultados
    """
    try:
        print(f"📥 Requisição recebida: {request.dict()}")
        
        # Processa a consulta no Airbnb
        resultado = processar_consulta(
            request.Dcheckin, 
            request.Dcheckout, 
            request.numero_hospede_numero
        )
        
        print(f"📤 Resultado da consulta: {resultado}")
        
        # Conecta ao Google Sheets
        print("🔗 Conectando ao Google Sheets...")
        client = conectar_google_sheets()
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Encontra a linha na planilha
        linha = encontrar_linha_planilha(
            sheet,
            request.id_do_contato,
            request.Dcheckin,
            request.Dcheckout
        )
        
        if linha:
            # Atualiza a planilha
            sucesso = atualizar_planilha(sheet, linha, resultado)
            
            if sucesso:
                return {
                    "status": "success",
                    "message": "Consulta realizada e planilha atualizada com sucesso",
                    "linha": linha,
                    "resultado": resultado
                }
            else:
                return {
                    "status": "error",
                    "message": "Consulta realizada mas erro ao atualizar planilha",
                    "resultado": resultado
                }
        else:
            return {
                "status": "error",
                "message": f"Linha não encontrada na planilha para ID={request.id_do_contato}",
                "resultado": resultado
            }
            
    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint legado para compatibilidade com site existente
@app.get("/executar")
def executar_legado(checkin: str, checkout: str, adultos: int, criancas: int = 0):
    """
    Endpoint legado para compatibilidade com o site www.praiadoscarneirosresort.com
    """
    try:
        hospedes = adultos + criancas
        data_in = datetime.strptime(checkin, "%Y-%m-%d")
        data_out = datetime.strptime(checkout, "%Y-%m-%d")
        numero_noites = (data_out - data_in).days

        resultados = []

        with sync_playwright() as p:
            for unidade in UNIDADES:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                
                def handle_route(route):
                    url = route.request.url
                    if any(domain in url for domain in [
                        'a0.muscache.com',
                        'www.googletagmanager.com',
                        'google-analytics.com',
                        'facebook.com',
                        'doubleclick.net',
                        'googlesyndication.com',
                        'googleadservices.com',
                        'googletag',
                        'analytics.js',
                        'gtag',
                        'fbevents.js'
                    ]):
                        route.abort()
                    else:
                        route.continue_()
                
                context.route("**/*", handle_route)
                page = context.new_page()
                
                print(f"🔍 Verificando: {unidade['nome']} ({unidade['id']})")
                url = (
                    f"https://www.airbnb.com.br/book/stays/{unidade['id']}"
                    f"?checkin={checkin}"
                    f"&checkout={checkout}"
                    f"&numberOfGuests={hospedes}"
                    f"&numberOfAdults={adultos}"
                    f"&numberOfChildren={criancas}"
                    f"&guestCurrency=BRL"
                    f"&productId={unidade['id']}"
                    f"&isWorkTrip=false"
                    f"&numberOfInfants=0&numberOfPets=0"
                )
                page.goto(url)
                page.wait_for_timeout(5000)

                content = page.content()
                match = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', content)
                if match:
                    preco_texto = match.group()
                    preco_limpo = preco_texto.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    preco_total = float(preco_limpo)
                    resultados.append({
                        "nome": unidade["nome"],
                        "preco": f"R$ {preco_total:.2f}",
                        "nota": "9.0",
                        "urlretorno": url,
                    })
                
                browser.close()

        return {"status": "ok", "resultado": resultados}

    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}
