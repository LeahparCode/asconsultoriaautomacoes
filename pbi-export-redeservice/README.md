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
2. **Conversão xlsx → csv sem Excel** (a parte mais escorregadia desse script). A versão original abria o Microsoft Excel de verdade (`win32com`, `SaveAs FileFormat=6`), que grava data em **DD/MM/AAAA** e número decimal com **vírgula**. `FileProcessor._valor_csv()` reproduz exatamente isso.

   **ATENÇÃO — não mude esse formato sem confirmar no gestão.** Já tentei "melhorar" isso renderizando a data conforme o `number_format` de cada célula (a coluna "Data filiação" vem com formato `mm-dd-yy` no Excel) — o RedeService **não leu a base assim**; o formato certo, confirmado com o usuário direto no sistema, é DD/MM/AAAA com barra. Ver o comentário em `_valor_csv()` antes de mexer aqui de novo.

   **Sempre confira o histórico de importação dentro do RedeService**, não só o log do script: o upload aparece como "sucesso" no script mesmo quando o backend rejeita o arquivo depois, de forma assíncrona.

3. **O RedeService não mostra nenhuma confirmação depois de clicar em "Enviar"** (nem toast, nem alerta — confirmado com o usuário, que também não vê nada ao importar manualmente). Por isso o script clicava em "Enviar" e já dava a importação como sucesso sem checar nada, mesmo quando o RedeService não processava o arquivo. `RedeServiceBot._confirmar_importacao_no_grid()` confere se surge uma linha nova no topo da grade de histórico contendo o nome do arquivo enviado — a mesma checagem manual que o usuário faz. Se não aparecer em até 180s, o script falha de verdade (e entra no retry) em vez de mentir dizendo que deu certo.

   **A leitura da grade é por texto (`_linha_mais_recente_da_grade()`), não por seletor CSS.** Tentei um seletor baseado no HTML que o usuário inspecionou manualmente (`td.grid-cell[data-name="log_arquivo"]`) e ele nunca deu match — mesmo com a grade visivelmente populada (confirmado no diagnóstico: o texto capturado mostrava cabeçalhos e linhas "CONCLUÍDO" certinho, mas o `presence_of_all_elements_located` nunca encontrava a célula). Por algum motivo o DOM real não bate com aquele seletor. A leitura via `body.text` (achar o cabeçalho "AÇÕES" e pegar a próxima linha não vazia) já provou duas vezes que funciona — se um dia quiser voltar a usar seletor CSS, inspecione o HTML de novo primeiro, não confie no seletor antigo.

4. **Evite `driver.get()` no fluxo de importação sempre que der.** Toda vez que o robô navegou por URL logo depois de uma importação, o RedeService derrubou a sessão (`.../Home/Login?sessaoInvalida=1`) — inclusive **entre uma base e outra**, mesmo com as anteriores importadas com sucesso. Por isso `importar_base()` só chama `abrir_pagina_importacao()` se `_grade_visivel()` disser que realmente saiu da tela de Importação: depois de uma importação confirmada, continuamos nela (a confirmação acabou de ler a grade ali mesmo), então é só clicar em "Novo" de novo.

5. **Cuidado ao navegar (`driver.get`) logo depois do "Enviar".** "Novo" abre um modal por cima da própria grade de histórico — a grade já está ali embaixo, sem precisar de reload. Uma primeira versão dessa checagem fazia um `driver.get()` na tela de Importação assim que clicava em "Enviar" pra conferir a grade, e isso coincidiu, de forma consistente e reproduzível, com o RedeService derrubando a sessão do robô (`.../Home/Login?sessaoInvalida=1`) bem nesse momento — mesmo sem ninguém mais logado com o mesmo usuário. Por isso `importar_base()` lê o topo da grade **antes** de abrir o modal (sem navegar, já que a grade já está na tela), e `_confirmar_importacao_no_grid()` primeiro tenta ler a grade na página atual depois do Enviar; só recorre a um `driver.get()` de recuperação depois de algumas tentativas falhando ali. Se `SessaoInvalidadaError` aparecer mesmo assim, é sinal de sessão concorrente de verdade (outro login ativo com o mesmo usuário) — nesse caso sim, esse robô precisaria de um login próprio no RedeService, separado de qualquer uso manual.

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
