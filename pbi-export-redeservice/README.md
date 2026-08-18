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

3. **O formulário de importação é aberto direto por URL** (`.../cobranca.be.cartaotodos/Importacao/Incluir`), não clicando no botão "Novo". Depois de logado, essa URL já cai no formulário. O clique no "Novo" (`demo-btn-addrow`) era o passo mais problemático do fluxo — o botão ficava "clicável" antes do Angular terminar o binding, o modal não abria, e a recuperação disso acabava refazendo login no meio da importação. Ir direto pela URL pula tudo isso.

4. **A sessão do RedeService não sobrevive a uma importação — cada base loga do zero.** Observado de forma consistente em várias execuções: depois que uma importação é enviada, o servidor invalida a sessão do robô. A primeira base (que roda logo após o login) sempre passava; as seguintes, reaproveitando a mesma sessão, caíam na tela de login (`.../Home/Login?sessaoInvalida=1`). Em vez de tentar preservar uma sessão que o servidor já considera morta, `importar_base()` chama `login_limpo()` antes de cada base a partir da segunda — limpa cookies/storage e loga de novo, recriando a condição que comprovadamente funciona.

5. **O upload do arquivo é feito em Playwright, não em Selenium — e isso é proposital.** A etapa do Power BI (acima no arquivo) roda em Selenium; só a `RedeServiceBot` usa Playwright. O motivo é o upload.

   No Selenium era preciso escrever o caminho no `<input type="file">` escondido e depois **forjar eventos de JavaScript** (`change` e um `drop` sintético com `DataTransfer`) pra convencer o Dropzone de que um arquivo tinha sido solto ali. O Dropzone até aceitava e mostrava o nome na tela, mas o servidor devolvia **HTTP 500** (página genérica de erro do IIS) e nada era importado — enquanto o mesmo arquivo, subido manualmente pelo navegador, entrava normalmente.

   `page.set_input_files()` anexa o arquivo pelo **protocolo nativo do navegador**, exatamente como um usuário escolhendo o arquivo na janela do sistema. Sem evento sintético nenhum. Se um dia alguém pensar em voltar essa parte pro Selenium: foi tentado, e é aqui que quebra.

   O `_garantir_upload_concluido()` continua conferindo o status real na API do Dropzone (`files[].status`: `queued` → `uploading` → `success`/`error`) antes de clicar em Enviar, e `_conferir_rejeicao()` falha de verdade se a tela mostrar mensagem de recusa depois do envio.

6. **O script não confirma se a importação foi realmente aceita.** Depois de clicar em "Enviar" ele imprime "enviada com sucesso" e segue — o RedeService não mostra confirmação nenhuma na tela (nem toast, nem alerta; nem manualmente aparece), então o script não tem como saber ali na hora se o backend aceitou o arquivo. **Confira o histórico de Importação dentro do RedeService** pra ter certeza.

   Cheguei a implementar uma checagem que voltava na grade de histórico pra confirmar a linha nova, mas ela foi revertida (18/08/2026) a pedido do usuário: qualquer navegação (`driver.get`) dentro do fluxo de importação fazia o RedeService derrubar a sessão do robô (`.../Home/Login?sessaoInvalida=1`), quebrando importações que antes passavam. Se for tentar isso de novo, o ponto de partida é: **não navegar** — ler a grade da página atual, já que "Novo" abre um modal por cima dela — e ler por texto, porque o seletor `td.grid-cell[data-name="log_arquivo"]` nunca deu match apesar da grade estar populada.

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
# Selenium 4.6+ baixa o chromedriver automaticamente (Selenium Manager),
# só precisa ter o Google Chrome instalado na máquina (usado no Power BI).
playwright install chromium   # usado na parte do RedeService
PBI_LOGIN_EMAIL=... PBI_SENHA=... RS_LOGIN=2 RS_SENHA=... PBI_HEADLESS=false python pbi_export.py
```

Com `PBI_HEADLESS=false` os dois navegadores abrem na tela e dá pra acompanhar o passo a passo — inclusive a importação no RedeService.

## Workflow

`.github/workflows/pbi-export.yml` — todo dia às ~07:53 (Brasília; deslocado alguns minutos da hora cheia pra sofrer menos atraso de fila do agendador do GitHub, veja o README da raiz), igual ao `ControladorPBI.py` original. Em caso de falha, tenta novamente até 3 vezes com 5 minutos de espera entre tentativas. Instala o Google Chrome no runner via `browser-actions/setup-chrome`. Pode ser disparado manualmente em **Actions → Power BI Export + Importacao RedeService → Run workflow**.

Os relatórios extraídos vão direto para a pasta de destino no Drive (sem subpasta por data), com a data no nome do arquivo (ex: `BASE_INADIMPLENCIA_13-08-2026.csv`) — se já existir um arquivo com esse mesmo nome (ou seja, rodou de novo no mesmo dia), ele é substituído em vez de duplicado; em outro dia, gera um arquivo novo.

Depois das 3 importações, o script conta quantas linhas cada base tinha (Inadimplência, Relacionamento, Vendas) e salva num `contagens.json` temporário — o workflow lê esse arquivo e alimenta o Resumo Diário no WhatsApp (veja a seção 8 do README da raiz).
