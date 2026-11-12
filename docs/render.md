# A API no Render

A API (`api_supabase.py`) roda no Render, no plano gratuito, em https://supermatch-api.onrender.com. Quase tudo se configura no painel do Render (o serviço `supermatch-api`); esta página guarda o que está lá, para não depender da memória de ninguém.

| Ajuste | Valor | Onde |
|---|---|---|
| Repositório e branch | `rafaelhsl/supermatch-api`, branch `main`. Cada merge na `main` publica sozinho | Settings → Build & Deploy |
| Build command | `pip install -r requirements-api.txt` | Settings → Build & Deploy |
| Start command | `uvicorn api_supabase:app --host 0.0.0.0 --port $PORT` | Settings → Build & Deploy |
| `SUPABASE_KEY` | a chave secreta do Supabase (a mesma do segredo `SUPABASE_KEY` do GitHub) | Environment |
| Versão do Python | `3.14.3`, fixada pelo arquivo `.python-version` do repositório | no repositório |
| Health Check Path | `/saude` | Settings (procure o campo "Health Check Path"; o nome do menu pode mudar) |
| Plano | gratuito: dorme após 15 minutos sem uso (veja `banco_de_dados.md`, "Manter o servidor acordado") | |

## Por que dois arquivos de bibliotecas

- `requirements-api.txt`: só o que a API importa (FastAPI, Uvicorn, Supabase, TheFuzz). É o que o Render instala.
- `requirements.txt`: tudo, ou seja, o da API mais o Playwright dos robôs. É o que a carga diária do GitHub instala.

Antes de separar, o Render instalava o Playwright (53 MB) e ainda baixava o Node.js 26 só por causa dele, sem a API usar nenhum dos dois. `tests/test_requirements.py` falha se alguém passar a importar na API um pacote que falta no `requirements-api.txt` (o deploy quebraria só no Render) ou se o Playwright entrar na API.

## Versão do Python

Sem o `.python-version`, o Render usa a versão mais nova que ele oferece, e ela muda sozinha (já era a 3.14.3 quando fixamos). O arquivo congela a que foi testada em produção. Para atualizar: troque o número no arquivo, abra um PR e confira o deploy. A carga do GitHub usa a 3.11 (`.github/workflows/main.yml`), que é outra coisa.

## Se o deploy falhar

O Render mantém a versão anterior no ar até a nova subir, então um build quebrado não derruba a API. Abra a aba Logs do deploy: erro de `pip` quase sempre é uma biblioteca nova que faltou no `requirements-api.txt`.
