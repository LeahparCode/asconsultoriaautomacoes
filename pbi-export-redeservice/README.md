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
2. **Conversão xlsx → csv sem Excel**: a versão original abria o Microsoft Excel de verdade (`win32com`) para salvar o CSV, que por padrão regional (pt-BR) usa `;` como separador e `cp1252` (ANSI/Windows-1252) como encoding — já reproduzido em `pbi_export.py` (constantes `CSV_DELIMITER`/`CSV_ENCODING`). Isso sozinho não foi suficiente: mesmo com `cp1252`, a base de Inadimplência continuou sendo rejeitada pelo backend com o mesmo erro de SQL (`LEFT`/`SUBSTRING`). Causa mais provável: `openpyxl` entrega datas/números como objetos Python "crus" (ex: `2026-08-13 00:00:00`, `1234.5`), e escrever isso direto no CSV não é o que o Excel real geraria (`13/08/2026`, `1234,5`) — o backend espera esse formato de largura fixa. `FileProcessor._valor_csv()` agora formata datas como `DD/MM/AAAA` e números decimais com vírgula antes de escrever no CSV. **Sempre confira o histórico de importação dentro do RedeService**, não só o log do script: o upload pode aparecer como "sucesso" no script mesmo quando o backend rejeita o arquivo de forma assíncrona.

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
