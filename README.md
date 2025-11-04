# Robô Airbnb - Integração Manychat

Robô automatizado para consulta de disponibilidade e preços de flats no Airbnb, integrado com Manychat.

## 📋 Funcionalidades

- Consulta automática de 2 unidades no Airbnb (Flat Colina e Flat Praia)
- Integração com Manychat via API
- Conversão automática de formatos de data
- Retorno estruturado de disponibilidade e preços
- Endpoint legado para compatibilidade com site existente

## 🚀 Deploy no Railway via GitHub

### Passo 1: Subir o código no GitHub

1. Acesse o repositório: https://github.com/flatcolina/robozap

2. No seu computador, abra o terminal e execute:

```bash
# Clone o repositório (se ainda não tiver feito)
git clone https://github.com/flatcolina/robozap.git
cd robozap

# Copie os arquivos do robô para esta pasta
# (main.py, requirements.txt, Dockerfile, .gitignore, README.md)

# Adicione os arquivos ao git
git add .

# Faça o commit
git commit -m "Adiciona robô de consulta Airbnb integrado com Manychat"

# Envie para o GitHub
git push origin main
```

### Passo 2: Configurar no Railway

1. Acesse https://railway.app e faça login

2. Clique em **"New Project"**

3. Selecione **"Deploy from GitHub repo"**

4. Escolha o repositório **flatcolina/robozap**

5. O Railway detectará automaticamente o Dockerfile e fará o deploy

6. Após o deploy, clique em **"Settings"** e depois em **"Generate Domain"** para obter a URL pública

7. Anote a URL pública (ex: `https://robozap-production.up.railway.app`)

## 🔗 Endpoints da API

### POST /consultar (Manychat)

Endpoint principal para integração com Manychat.

**URL:** `https://sua-url-railway.up.railway.app/consultar`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "Dcheckin": "25/12/2024",
  "Dcheckout": "30/12/2024",
  "numero_hospede_numero": 4
}
```

**Resposta:**
```json
{
  "flat_colina_disponivel": "sim",
  "flat_colina_preco": "R$ 3.500,00",
  "flat_colina_url": "https://www.airbnb.com.br/book/stays/...",
  "flat_praia_disponivel": "sim",
  "flat_praia_preco": "R$ 4.200,00",
  "flat_praia_url": "https://www.airbnb.com.br/book/stays/...",
  "numero_noites": 5,
  "checkin": "25/12/2024",
  "checkout": "30/12/2024",
  "hospedes": 4
}
```

### GET /executar (Legado)

Endpoint compatível com o site www.praiadoscarneirosresort.com

**URL:** `https://sua-url-railway.up.railway.app/executar?checkin=2024-12-25&checkout=2024-12-30&adultos=4&criancas=0`

### GET /health

Verifica se o serviço está funcionando.

**URL:** `https://sua-url-railway.up.railway.app/health`

## 🤖 Configuração no Manychat

### Variáveis que você precisa criar no Manychat:

#### Variáveis de ENTRADA (que o usuário fornece):
1. **Dcheckin** (Texto) - Data de check-in no formato DD/MM/AAAA
2. **Dcheckout** (Texto) - Data de check-out no formato DD/MM/AAAA
3. **numero_hospede_numero** (Número) - Quantidade de hóspedes

#### Variáveis de SAÍDA (que o robô retorna):

**Para o Flat Colina:**
1. **flat_colina_disponivel** (Texto) - Valores: "sim" ou "nao"
2. **flat_colina_preco** (Texto) - Ex: "R$ 3.500,00" ou vazio se indisponível
3. **flat_colina_url** (Texto) - URL da reserva ou vazio se indisponível

**Para o Flat Praia:**
4. **flat_praia_disponivel** (Texto) - Valores: "sim" ou "nao"
5. **flat_praia_preco** (Texto) - Ex: "R$ 4.200,00" ou vazio se indisponível
6. **flat_praia_url** (Texto) - URL da reserva ou vazio se indisponível

**Informações adicionais:**
7. **numero_noites** (Número) - Quantidade de noites calculada
8. **checkin** (Texto) - Data de check-in confirmada
9. **checkout** (Texto) - Data de check-out confirmada
10. **hospedes** (Número) - Número de hóspedes confirmado

### Como configurar a ação External Request no Manychat:

1. No flow do Manychat, adicione uma ação **"External Request"**

2. Configure:
   - **Request Type:** POST
   - **URL:** `https://sua-url-railway.up.railway.app/consultar`
   - **Headers:** 
     - `Content-Type: application/json`

3. **Body (JSON):**
```json
{
  "Dcheckin": "{{Dcheckin}}",
  "Dcheckout": "{{Dcheckout}}",
  "numero_hospede_numero": {{numero_hospede_numero}}
}
```

4. **Set Custom Fields:** Mapeie as respostas para as variáveis:
   - `flat_colina_disponivel` → Custom Field: flat_colina_disponivel
   - `flat_colina_preco` → Custom Field: flat_colina_preco
   - `flat_colina_url` → Custom Field: flat_colina_url
   - `flat_praia_disponivel` → Custom Field: flat_praia_disponivel
   - `flat_praia_preco` → Custom Field: flat_praia_preco
   - `flat_praia_url` → Custom Field: flat_praia_url
   - `numero_noites` → Custom Field: numero_noites

5. Adicione condições após a requisição para verificar disponibilidade:
   - Se `flat_colina_disponivel` = "sim" → Mostrar preço e botão de reserva
   - Se `flat_colina_disponivel` = "nao" → Informar indisponibilidade

## 📝 Exemplo de Fluxo no Manychat

```
1. Bot: "Qual a data de check-in? (DD/MM/AAAA)"
   → Salvar resposta em: Dcheckin

2. Bot: "Qual a data de check-out? (DD/MM/AAAA)"
   → Salvar resposta em: Dcheckout

3. Bot: "Quantas pessoas?"
   → Salvar resposta em: numero_hospede_numero

4. Ação: External Request (POST /consultar)

5. Condição: Se flat_colina_disponivel = "sim"
   → Bot: "✅ Flat Colina disponível por {{flat_colina_preco}}"
   → Botão: "Reservar Flat Colina" → Abrir {{flat_colina_url}}

6. Condição: Se flat_praia_disponivel = "sim"
   → Bot: "✅ Flat Praia disponível por {{flat_praia_preco}}"
   → Botão: "Reservar Flat Praia" → Abrir {{flat_praia_url}}

7. Condição: Se ambos = "nao"
   → Bot: "😔 Infelizmente não há disponibilidade para essas datas."
```

## 🔧 Desenvolvimento Local

Para testar localmente:

```bash
# Instalar dependências
pip install -r requirements.txt
playwright install

# Executar servidor
uvicorn main:app --reload

# Testar
curl -X POST http://localhost:8000/consultar \
  -H "Content-Type: application/json" \
  -d '{
    "Dcheckin": "25/12/2024",
    "Dcheckout": "30/12/2024",
    "numero_hospede_numero": 4
  }'
```

## 📊 Diferenças entre os Endpoints

| Característica | /consultar (Manychat) | /executar (Site) |
|----------------|----------------------|------------------|
| Método | POST | GET |
| Formato data entrada | DD/MM/AAAA | AAAA-MM-DD |
| Parâmetros | JSON body | Query string |
| Retorna disponibilidade | ✅ Sim | ❌ Não |
| Retorna preços separados | ✅ Sim | ✅ Sim |
| URLs individuais | ✅ Sim | ✅ Sim |

## 🛠️ Tecnologias

- **FastAPI** - Framework web
- **Playwright** - Automação de navegador
- **Pydantic** - Validação de dados
- **Uvicorn** - Servidor ASGI
- **Docker** - Containerização

## 📞 Suporte

Após o deploy, envie a URL pública do Railway para configurar a integração final com o Manychat.

## 📄 Licença

Projeto proprietário - Flat Colina / Praia dos Carneiros Resort
