# Power BI Export + Importação RedeService

Exporta 3 relatórios do Power BI (Inadimplência, Relacionamento, Vendas), converte o primeiro para CSV e reimporta os três no RedeService.

## Secrets necessários

| Secret | Valor |
|---|---|
| `PBI_LOGIN_EMAIL` | e-mail de login do Power BI |
| `PBI_SENHA` | senha do Power BI |
| `RS_LOGIN` | usuário do RedeService |
| `RS_SENHA` | senha do RedeService |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON da conta de serviço do Google (opcional, para backup no Drive) |
| `GDRIVE_FOLDER_PBI_ID` | ID da pasta "Relatorios PBI" no Drive (opcional) |

## ⚠️ Pontos de atenção

1. **Login Microsoft/MFA**: o login do Power BI passa pela tela da Microsoft. Se a conta tiver MFA ativo, a automação trava em modo headless — veja o README da raiz.
2. **Conversão xlsx → csv sem Excel**: a versão original abria o Microsoft Excel de verdade (`win32com`) para salvar o CSV, e por padrão regional (pt-BR) o Excel salva CSV com `;` como separador. Reproduzi esse comportamento em `pbi_export.py` (constantes `CSV_DELIMITER` e `CSV_ENCODING` no topo do arquivo), mas **valide o primeiro arquivo importado no RedeService** — se a importação falhar por formato, ajuste essas duas constantes.

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
# Selenium 4.6+ baixa o chromedriver automaticamente (Selenium Manager),
# só precisa ter o Google Chrome instalado na máquina.
PBI_LOGIN_EMAIL=... PBI_SENHA=... RS_LOGIN=2 RS_SENHA=... PBI_HEADLESS=false python pbi_export.py
```

## Workflow

`.github/workflows/pbi-export.yml` — cron provisório: dias úteis às 08:00 (Brasília). Instala o Google Chrome no runner via `browser-actions/setup-chrome`. Pode ser disparado manualmente em **Actions → Power BI Export + Importacao RedeService → Run workflow**.
