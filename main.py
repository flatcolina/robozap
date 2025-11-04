
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright
from datetime import datetime
from pydantic import BaseModel, validator
from typing import Optional
import re

app = FastAPI(title="Robô Airbnb - Manychat Integration")

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

class ManychatRequest(BaseModel):
    Dcheckin: str  # Formato DD/MM/AAAA
    Dcheckout: str  # Formato DD/MM/AAAA
    numero_hospede_numero: int
    
    @validator('numero_hospede_numero')
    def validar_hospedes(cls, v):
        if v < 1:
            raise ValueError('Deve haver pelo menos 1 hóspede')
        if v > 20:
            raise ValueError('Número máximo de hóspedes é 20')
        return v
    
    @validator('Dcheckin', 'Dcheckout')
    def validar_formato_data(cls, v):
        try:
            datetime.strptime(v, "%d/%m/%Y")
            return v
        except ValueError:
            raise ValueError(f'Data inválida: {v}. Use o formato DD/MM/AAAA')

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
        adultos = hospedes  # Considera todos como adultos
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
                    
                    # Abre novo browser para cada unidade
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    
                    # Bloqueia recursos desnecessários
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
                    
                    # Verifica se está disponível procurando por mensagens de indisponibilidade
                    indisponivel_patterns = [
                        "não está disponível",
                        "não disponível",
                        "not available",
                        "já está reservada",
                        "already booked"
                    ]
                    
                    esta_indisponivel = any(pattern.lower() in content.lower() for pattern in indisponivel_patterns)
                    
                    # Procura por preço
                    match = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', content)
                    
                    if match and not esta_indisponivel:
                        preco_texto = match.group()
                        preco_limpo = preco_texto.replace("R$", "").replace(".", "").replace(",", ".").strip()
                        preco_total = float(preco_limpo)
                        preco_formatado = f"R$ {preco_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        print(f"✅ Disponível - Preço: {preco_formatado}")
                        
                        # Atualiza resultado baseado na chave da unidade
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
        "servico": "Robô Airbnb - Integração Manychat",
        "versao": "2.1",
        "endpoints": {
            "consultar_post": "POST /consultar (JSON body)",
            "consultar_get": "GET /consultar?Dcheckin=DD/MM/AAAA&Dcheckout=DD/MM/AAAA&numero_hospede_numero=N",
            "executar": "GET /executar (legado)",
            "health": "GET /health"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Endpoint POST para Manychat (formato JSON)
@app.post("/consultar")
def consultar_post(request: ManychatRequest):
    """
    Endpoint para consulta via Manychat (POST com JSON)
    
    Recebe:
    - Dcheckin: Data de check-in no formato DD/MM/AAAA
    - Dcheckout: Data de check-out no formato DD/MM/AAAA
    - numero_hospede_numero: Número de hóspedes
    
    Retorna:
    - flat_colina_disponivel: "sim" ou "nao"
    - flat_colina_preco: Preço total (ex: "R$ 1.500,00") ou ""
    - flat_colina_url: URL da reserva ou ""
    - flat_praia_disponivel: "sim" ou "nao"
    - flat_praia_preco: Preço total (ex: "R$ 1.800,00") ou ""
    - flat_praia_url: URL da reserva ou ""
    - numero_noites: Número de noites
    """
    return processar_consulta(request.Dcheckin, request.Dcheckout, request.numero_hospede_numero)

# Endpoint GET para testes e compatibilidade
@app.get("/consultar")
def consultar_get(
    Dcheckin: str = Query(..., description="Data de check-in no formato DD/MM/AAAA"),
    Dcheckout: str = Query(..., description="Data de check-out no formato DD/MM/AAAA"),
    numero_hospede_numero: int = Query(..., description="Número de hóspedes")
):
    """
    Endpoint para consulta via GET (para testes)
    
    Exemplo: /consultar?Dcheckin=25/12/2024&Dcheckout=30/12/2024&numero_hospede_numero=4
    """
    # Valida os dados usando o modelo Pydantic
    try:
        request_data = ManychatRequest(
            Dcheckin=Dcheckin,
            Dcheckout=Dcheckout,
            numero_hospede_numero=numero_hospede_numero
        )
        return processar_consulta(request_data.Dcheckin, request_data.Dcheckout, request_data.numero_hospede_numero)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint legado para compatibilidade com site existente
@app.get("/executar")
def executar_legado(checkin: str, checkout: str, adultos: int, criancas: int = 0):
    """
    Endpoint legado para compatibilidade com o site www.praiadoscarneirosresort.com
    Mantém o formato original de resposta
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
                print(f"🌐 URL acessada: {url}")
                page.goto(url)
                page.wait_for_timeout(5000)

                content = page.content()
                match = re.search(r'R\$\s?\d{1,3}(\.\d{3})*,\d{2}', content)
                if match:
                    preco_texto = match.group()
                    preco_limpo = preco_texto.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    preco_total = float(preco_limpo)
                    print(f"✅ Preço encontrado para {unidade['nome']}: {match.group()}")
                    resultados.append({
                        "nome": unidade["nome"],
                        "preco": f"R$ {preco_total:.2f}",
                        "nota": "9.0",
                        "urlretorno": url,
                    })
                
                browser.close()
                print(f"🔄 Navegador fechado para {unidade['nome']}")

            print("🔚 Consulta finalizada.")

        return {"status": "ok", "resultado": resultados}

    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}
