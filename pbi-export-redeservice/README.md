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
2. **Conversão xlsx → csv sem Excel** (a parte mais escorregadia desse script). A versão original abria o Microsoft Excel de verdade (`win32com`, `SaveAs FileFormat=6`). O ponto que me custou três tentativas: o Excel **não grava o valor cru da célula no CSV — ele grava o valor JÁ FORMATADO, do jeito que aparece na tela**, segundo o `number_format` daquela célula. O `openpyxl` entrega o valor cru, e é aí que quebra.

   O caso concreto: a coluna **"Data filiação"** tem `number_format = mm-dd-yy`. O Excel gravava `08-17-26` (mês-dia-ano, com **traço**). Escrevendo o valor cru vira `17/08/2026 09:23:45` — sem traço nenhum. A procedure do RedeService fatia essa data procurando o traço, o `CHARINDEX` volta 0, o length vira -1 e estoura `Invalid length parameter passed to the LEFT or SUBSTRING function`. Mesma história nas colunas de dinheiro (`"R$"\ #,##0.00`): o Excel gravava `R$ 1.234,50`, o valor cru era `1234.5`.

   Por isso `FileProcessor._valor_csv()` recebe a **célula** (não só o valor) e renderiza respeitando o `number_format`, via `_render_data()` e `_render_numero()`. Se alguma coluna nova sair errada na importação, é aí que se mexe.

   **Sempre confira o histórico de importação dentro do RedeService**, não só o log do script: o upload aparece como "sucesso" no script mesmo quando o backend rejeita o arquivo depois, de forma assíncrona.

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
# Selenium 4.6+ baixa o chromedriver automaticamente (Selenium Manager),
# só precisa ter o Google Chrome instalado na máquina.
PBI_LOGIN_EMAIL=... PBI_SENHA=... RS_LOGIN=2 RS_SENHA=... PBI_HEADLESS=false python pbi_export.py
```

## Workflow

`.github/workflows/pbi-export.yml` — todo dia às ~07:53 (Brasília; deslocado alguns minutos da hora cheia pra sofrer menos atraso de fila do agendador do GitHub, veja o README da raiz), igual ao `ControladorPBI.py` original. Em caso de falha, tenta novamente até 3 vezes com 5 minutos de espera entre tentativas. Instala o Google Chrome no runner via `browser-actions/setup-chrome`. Pode ser disparado manualmente em **Actions → Power BI Export + Importacao RedeService → Run workflow**.

Os relatórios extraídos vão direto para a pasta de destino no Drive (sem subpasta por data), com a data no nome do arquivo (ex: `BASE_INADIMPLENCIA_13-08-2026.csv`) — se já existir um arquivo com esse mesmo nome (ou seja, rodou de novo no mesmo dia), ele é substituído em vez de duplicado; em outro dia, gera um arquivo novo.

Depois das 3 importações, o script conta quantas linhas cada base tinha (Inadimplência, Relacionamento, Vendas) e salva num `contagens.json` temporário — o workflow lê esse arquivo e alimenta o Resumo Diário no WhatsApp (veja a seção 8 do README da raiz).
