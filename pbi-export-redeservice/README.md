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

1. **Este script é o do usuário, portado.** Em 18/08/2026 o usuário trouxe uma versão do `pbi_export.py` que roda na máquina dele (Windows) e importa no RedeService sem problemas. Ela substituiu a versão anterior. A classe `RedeServiceBot` é **idêntica à do usuário**, de propósito: é a parte que funciona, e mexer nela já custou muito tempo. As adaptações pro GitHub Actions ficaram todas fora dela (credenciais por secrets, pasta de download, headless, conversão de CSV, Drive e contagens).

2. **Login Microsoft/MFA**: o login do Power BI passa pela tela da Microsoft. Se a conta tiver MFA ativo, a automação trava em modo headless — veja o README da raiz.

3. **Conversão xlsx → csv sem Excel** — a única diferença real de comportamento em relação ao script do usuário. O original abre o Microsoft Excel de verdade (`win32com`, `SaveAs FileFormat=6`); os runners do GitHub não têm Office, então `FileProcessor.processar_planilha_inadimplencia()` faz a conversão com `openpyxl` + `csv.writer`, reproduzindo o mesmo resultado: delimitador `;`, encoding **cp1252** (ANSI, o padrão do "Salvar como CSV" do Excel em pt-BR — **não** utf-8) e data em **DD/MM/AAAA** com decimal por vírgula.

   **ATENÇÃO — não mude esse formato sem confirmar no gestão.** Já se tentou renderizar a data conforme o `number_format` de cada célula (a coluna "Data filiação" vem como `mm-dd-yy`): o RedeService **não leu a base assim**. Ver o comentário em `_valor_csv()` antes de mexer.

   Se algum dia a importação da Inadimplência voltar a falhar e a de Relacionamento/Vendas (que sobem o `.xlsx` direto, sem conversão) continuar passando, **é aqui que se olha primeiro** — é o único ponto onde o arquivo gerado no runner difere do gerado na máquina do usuário.

4. **O script não confirma se a importação foi aceita.** Depois de clicar em "Enviar" ele imprime "enviada com sucesso" e segue. O RedeService não mostra confirmação nenhuma na tela (nem manualmente aparece), então o script não tem como saber ali na hora se o backend aceitou. **Confira o histórico de Importação dentro do RedeService** pra ter certeza.

5. **Franquias**: Ilhéus foi removido de todos os relatórios (`FRANQUIAS` e `FRANQUIAS_VENDAS`), conforme a versão do usuário de 18/08/2026.

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
# Selenium 4.6+ baixa o chromedriver automaticamente (Selenium Manager),
# só precisa ter o Google Chrome instalado na máquina.
PBI_LOGIN_EMAIL=... PBI_SENHA=... RS_LOGIN=2 RS_SENHA=... PBI_HEADLESS=false python pbi_export.py
```

Com `PBI_HEADLESS=false` os dois navegadores abrem na tela e dá pra acompanhar o passo a passo — inclusive a importação no RedeService.

## Workflow

`.github/workflows/pbi-export.yml` — todo dia às ~07:53 (Brasília; deslocado alguns minutos da hora cheia pra sofrer menos atraso de fila do agendador do GitHub, veja o README da raiz), igual ao `ControladorPBI.py` original. Em caso de falha, tenta novamente até 3 vezes com 5 minutos de espera entre tentativas. Instala o Google Chrome no runner via `browser-actions/setup-chrome`. Pode ser disparado manualmente em **Actions → Power BI Export + Importacao RedeService → Run workflow**.

Os relatórios extraídos vão direto para a pasta de destino no Drive (sem subpasta por data), com a data no nome do arquivo (ex: `BASE_INADIMPLENCIA_13-08-2026.csv`) — se já existir um arquivo com esse mesmo nome (ou seja, rodou de novo no mesmo dia), ele é substituído em vez de duplicado; em outro dia, gera um arquivo novo.

Depois das 3 importações, o script conta quantas linhas cada base tinha (Inadimplência, Relacionamento, Vendas) e salva num `contagens.json` temporário — o workflow lê esse arquivo e alimenta o Resumo Diário no WhatsApp (veja a seção 8 do README da raiz).
