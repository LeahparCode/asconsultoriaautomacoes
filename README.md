# AS Consultoria — Automações

Repositório com as automações web (Playwright/Selenium) que uso pra rodar os processos do dia a dia sem precisar tocar em nada, uma pasta por automação:

| Pasta | O que faz | Sistema | Horário (BRT) |
|---|---|---|---|
| [`gerar-perfil-redeservice/`](gerar-perfil-redeservice) | Dispara a "Geração de Perfil" no RedeService | RedeService (Cartão de Todos) | segunda a sexta, 08:30 |
| [`evo-inadimplentes/`](evo-inadimplentes) | Extrai clientes inadimplentes (Salvador + Pernambués) | EVO / AllpFit | todos os dias, 07:00 |
| [`pbi-export-redeservice/`](pbi-export-redeservice) | Exporta 3 relatórios do Power BI e reimporta no RedeService | Power BI + RedeService | todos os dias, 07:40 |
| [`tableau-agendamentos/`](tableau-agendamentos) | Exporta relatório de agendamentos do mês corrente | Tableau (AmorSaúde) | **de hora em hora, 08h às 18h**, segunda a sábado |

Esses horários vieram dos controladores que eu já usava antes (`ControladorGerarPerfil.py`, `ControladorEVO.py`, `ControladorPBI.py`, `Controlador.py`).

> ⚠️ **Importante: quem dispara essas automações NÃO é o `schedule:` do GitHub Actions.** Eu deixei ele comentado de propósito nos 4 `.yml` (dentro de `.github/workflows/`) — não é bug, é assim mesmo. Explico o motivo e como funciona de verdade logo abaixo, na seção 6.

> **Atenção — Tableau roda até 11x por dia.** O `Controlador.py` original não faz uma extração única por mês: ele reexecuta o script **toda hora cheia** dentro do expediente (08h-18h, seg-sáb) pra manter o relatório sempre atualizado, e reproduzi esse comportamento. Isso dá ~66 execuções de navegador por semana só dessa automação.

> **19/08/2026 — o repositório é público, e todas as automações rodam no runner do próprio GitHub (`ubuntu-latest`).** A soma dos minutos das 4 automações com navegador (principalmente o Tableau, de hora em hora) estourou rápido a cota gratuita de Actions de repositório privado. Cheguei a cogitar um runner self-hosted numa VM gratuita (Oracle Cloud Always Free), mas travou no cadastro: a Oracle exige cartão de crédito físico e rejeita débito/pré-pago, inclusive cartão virtual — não tenho cartão de crédito. Sem VM grátis viável e sem querer deixar o PC ligado o dia todo como runner, a saída sem custo foi tornar o repositório **público**: Actions em repo público é ilimitado e gratuito, sem cartão. Detalhes e o que isso mudou na seção 9.

## O que mudou em relação aos scripts originais

Os scripts originais rodavam no meu computador (Windows, com Google Drive Desktop mapeado como unidade `G:\` e, num caso, o Microsoft Excel instalado). Isso não existe num runner do GitHub Actions (uma máquina Linux efêmera na nuvem), então adaptei cada script:

1. **Sem senha no código.** Todo login/senha vem de variáveis de ambiente, preenchidas a partir de **GitHub Secrets** (nunca aparecem no código-fonte nem nos logs).
2. **Sem `G:\...` (Google Drive Desktop).** Os arquivos baixados são salvos numa pasta temporária local (dentro do runner) e depois enviados à mesma estrutura de pastas do Drive via **Google Drive API**. Antes de o repositório ficar público, se o upload falhasse o arquivo ficava disponível pra download manual em **Actions → (execução) → Artifacts**; **desde 19/08/2026 isso não existe mais pra `evo-inadimplentes`, `pbi-export-redeservice` e `tableau-agendamentos`** — esses relatórios têm dado pessoal de cliente (CPF, nome, dívida, agendamento), e artefato de execução em repo público é baixável por qualquer pessoa. Se o upload pro Drive falhar agora, o arquivo só existe no runner (efêmero) — peça pra eu ler o log da execução se precisar investigar. `gerar-perfil-redeservice` não tem relatório nenhum (só um clique de sistema) e continua subindo screenshot de erro como artefato normalmente, sem esse risco.
3. **Sem Excel/`win32com`** (só no `pbi-export-redeservice`). A conversão de `.xlsx` pra `.csv` que dependia de abrir o Excel de verdade foi reescrita usando só `openpyxl`, sem precisar do Office instalado.

## Passo a passo geral de configuração

### 1. Configurar o upload para o Google Drive

O código suporta 3 formas de autenticar no Drive (`evo-inadimplentes/gdrive_utils.py`, `pbi-export-redeservice/gdrive_utils.py`, `tableau-agendamentos/gdrive_utils.py` — são idênticos). Ele tenta nesta ordem: **OAuth de usuário** (se configurado) → **conta de serviço com Delegação de domínio** (se `GDRIVE_IMPERSONATE_USER` configurado) → **conta de serviço pura**. Escolhi a Opção A abaixo, mas deixo as outras documentadas caso precise trocar.

#### Opção A — OAuth como eu mesmo (recomendado, não precisa de Workspace)

A automação passa a agir como se fosse eu mesmo (minha conta Google normal), usando minha própria cota de armazenamento — funciona com qualquer conta Google, com ou sem Workspace, sem precisar de admin nem de conta de serviço.

1. No [Google Cloud Console](https://console.cloud.google.com/), criei um projeto e ativei a **Google Drive API** em "APIs e serviços" → "Biblioteca".
2. Fui em "APIs e serviços" → "Credenciais" → "Criar credenciais" → **ID do cliente OAuth**.
   - Configurei a "Tela de consentimento OAuth" como **Externo**, preenchi nome/e-mail, e adicionei meu próprio e-mail em "Usuários de teste" (não precisa publicar o app — modo de teste já é suficiente pro meu uso).
   - Tipo de aplicativo: **Aplicativo para computador**.
   - Anotei o **Client ID** e o **Client secret** gerados.
3. No meu computador, rodei o script `scripts/gerar_refresh_token_drive.py` (instruções no topo do arquivo): ele abre o navegador, faço login com a conta que tem acesso às pastas de destino e autorizo — no final ele imprime os 3 valores prontos pra colar nos Secrets do GitHub.
4. Peguei o **ID de cada pasta de destino** (Relatórios EVO, Relatorios PBI, Agendamentos) sem precisar mover nada: abro a pasta no navegador e copio o trecho final da URL, depois de `folders/`.
   `https://drive.google.com/drive/folders/1AbCdEfGhIjKlmNoPQRstuVWxyz` → o ID é `1AbCdEfGhIjKlmNoPQRstuVWxyz`.

> **O refresh token pode expirar/ser revogado** (aconteceu em 19/08/2026 — todas as execuções daquele dia falharam o upload com `invalid_grant: Token has been expired or revoked`, sem afetar o resto do script). Se acontecer de novo: gere um novo Client Secret em [Google Cloud Console → Credenciais](https://console.cloud.google.com/apis/credentials) (clique no cliente OAuth existente → "Add secret" — o Google só mostra o secret uma vez na criação, não dá pra recuperar o antigo), rode `scripts/gerar_refresh_token_drive.py` de novo com o Client ID/Secret, e atualize os 3 Secrets (`GDRIVE_OAUTH_CLIENT_ID`, `GDRIVE_OAUTH_CLIENT_SECRET`, `GDRIVE_OAUTH_REFRESH_TOKEN`) no GitHub.

#### Opção B — Conta de serviço (exige Google Workspace)

Contas de serviço **não têm cota de armazenamento própria** — enviar arquivo pra uma pasta comum do "Meu Drive" (mesmo compartilhada como Editor) falha com `storageQuotaExceeded`. Duas formas de contornar isso, ambas exigindo um plano Workspace completo (Business/Enterprise, não o plano Individual):

- **Delegação em todo o domínio**: a conta de serviço age como um usuário Workspace real, usando a cota dele (mantém as pastas onde já estão). No Cloud Console, abra a conta de serviço → "Detalhes avançados" → ative a Delegação → anote o "ID do cliente" → no [Admin Console](https://admin.google.com/) (precisa ser admin): Segurança → Controles de acesso e dados → Controles de API → Delegação em todo o domínio → Adicionar novo (Client ID + escopo `https://www.googleapis.com/auth/drive`) → defina `GDRIVE_IMPERSONATE_USER` com o e-mail representado.
- **Drive Compartilhada**: crie uma Drive Compartilhada, mova as pastas de destino pra dentro dela, e adicione o e-mail da conta de serviço como membro (Gerenciador de conteúdo ou superior). Não precisa de `GDRIVE_IMPERSONATE_USER`.

Em ambos os casos: crie a conta de serviço em "APIs e serviços" → "Credenciais" → "Criar credenciais" → Conta de serviço → aba "Chaves" → "Criar nova chave" → JSON (esse arquivo vai inteiro no Secret `GDRIVE_SERVICE_ACCOUNT_JSON`).

### 2. Cadastrar os Secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Criei estes secrets:

| Secret | Usado por | Valor |
|---|---|---|
| `RS_LOGIN` | Gerar Perfil, PBI Export | usuário do RedeService |
| `RS_SENHA` | Gerar Perfil, PBI Export | senha do RedeService |
| `EVO_LOGIN` | EVO Inadimplentes | e-mail de login do EVO |
| `EVO_SENHA` | EVO Inadimplentes | senha do EVO |
| `PBI_LOGIN_EMAIL` | PBI Export | e-mail de login do Power BI |
| `PBI_SENHA` | PBI Export | senha do Power BI |
| `TABLEAU_EMAIL` | Tableau Agendamentos | e-mail de login do Tableau |
| `TABLEAU_SENHA` | Tableau Agendamentos | senha do Tableau |
| `GDRIVE_FOLDER_EVO_ID` | EVO Inadimplentes | ID da pasta "Relatórios EVO" no Drive |
| `GDRIVE_FOLDER_PBI_ID` | PBI Export | ID da pasta "Relatorios PBI" no Drive |
| `GDRIVE_FOLDER_TABLEAU_ID` | Tableau Agendamentos | ID da pasta "Agendamentos" no Drive |
| `CALLMEBOT_PHONE` | Notificação de falha (todas) | meu número de WhatsApp com código do país, sem `+` (ex: `5571999999999`) |
| `CALLMEBOT_APIKEY` | Notificação de falha (todas) | apikey que o bot do CallMeBot manda por WhatsApp na ativação — veja a seção 7 |

E, dependendo da opção escolhida no passo 1 pro upload no Drive:

| Secret | Opção | Valor |
|---|---|---|
| `GDRIVE_OAUTH_CLIENT_ID` | A — OAuth de usuário | Client ID gerado no Cloud Console |
| `GDRIVE_OAUTH_CLIENT_SECRET` | A — OAuth de usuário | Client secret gerado no Cloud Console |
| `GDRIVE_OAUTH_REFRESH_TOKEN` | A — OAuth de usuário | Impresso por `scripts/gerar_refresh_token_drive.py` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | B — Conta de serviço | **conteúdo inteiro** do arquivo `.json` da conta de serviço |
| `GDRIVE_IMPERSONATE_USER` | B — Conta de serviço + Delegação de domínio | e-mail do usuário Workspace representado (deixe sem definir se for usar Drive Compartilhada) |

Todas as senhas acima estavam em texto puro nos scripts originais — troquei por variável de ambiente e **não existem mais em nenhum arquivo do repositório**.

### 3. Testar manualmente antes de confiar em qualquer agendamento

Em cada workflow, na aba **Actions** do GitHub, escolho o workflow → **Run workflow** (botão à direita) pra disparar uma execução manual (`workflow_dispatch`) sem esperar horário nenhum. Isso é essencial pra validar login, seletores e o upload no Drive antes de deixar rodando sozinho.

### 4. Ressalvas importantes por automação

- **`pbi-export-redeservice`**: a conversão de Excel pra CSV foi refeita sem o Excel, usando delimitador `;`, encoding `cp1252` (ANSI/Windows-1252) e — o pulo do gato — cada célula **renderizada segundo o `number_format` dela**, porque é isso que o Excel grava no CSV (o valor que aparece na tela, não o valor cru). Ex: a coluna "Data filiação" tem formato `mm-dd-yy`, então tem que sair `08-17-26`, não `17/08/2026`. Detalhes no [README da pasta](pbi-export-redeservice). **Atenção**: essa base já teve rejeições silenciosas do backend do RedeService (a tela de upload dizia "sucesso", mas o histórico de importação mostrava erro de SQL `LEFT`/`SUBSTRING`) — **sempre confiro o histórico de importação dentro do RedeService**, não só o log do script, pra confirmar que a importação realmente foi processada.
- **`pbi-export-redeservice`** e **`tableau-agendamentos`**: os logins passam pela tela da Microsoft (Azure AD). Se a conta usada tiver **MFA (autenticação multifator)** ativo, a automação trava no GitHub Actions (não dá pra responder ao código MFA num runner headless). Se acontecer, é preciso isentar essa conta de MFA no Microsoft 365 ou usar uma conta de serviço dedicada sem MFA.
- **`evo-inadimplentes`**: usa o canal `chrome` real do navegador (não o Chromium genérico) pra reduzir detecção de automação — o workflow já instala isso via `playwright install --with-deps chrome`.

### 5. Estrutura de cada pasta

Cada automação é independente: tem seu próprio script Python, `requirements.txt` e (quando precisa enviar arquivo ao Drive) `gdrive_utils.py`. Veja o README de cada pasta pra detalhes específicos.

### 6. Agendamento de verdade: cron-job.org, não o `schedule:` do GitHub

Essa foi a parte mais chata de acertar, então vale documentar bem o porquê.

**O problema**: o `schedule:` nativo do GitHub Actions não dispara no minuto exato. Ele entra numa fila, e em horário de pico — principalmente bem na hora cheia (`:00`), que é quando o maior volume de workflows do GitHub inteiro dispara junto — o atraso passa fácil de 10-20 minutos. Cheguei a tentar contornar isso deslocando os horários pra minutos "quebrados" tipo `:07`, `:13`, `:29` (fora dos múltiplos de 5), mas isso só reduz o problema, não resolve.

**A solução**: tirei o GitHub de responsabilidade pelo horário e passei isso pra um agendador externo, o [cron-job.org](https://cron-job.org) (gratuito, sem limite de jobs). Cada uma das 4 automações tem um job lá que, no horário exato, faz uma chamada `POST` direto pra API do GitHub:

```
POST https://api.github.com/repos/LeahparCode/asconsultoriaautomacoes/actions/workflows/<arquivo>.yml/dispatches
Authorization: Bearer <token>
Content-Type: application/json

{"ref":"Nomain"}
```

Isso dispara o workflow quase instantaneamente, sem cair na fila do `schedule:`. Por isso os 4 `.yml` em `.github/workflows/` têm o bloco `schedule:` **comentado** — deixei documentado ali dentro qual era o cron, só de referência, mas quem manda no horário agora é o painel do cron-job.org, não esse arquivo.

**O que precisa pra isso funcionar (e pra mexer nos horários no futuro):**

1. Um **Personal Access Token do GitHub (fine-grained)**, criado em `github.com/settings/personal-access-tokens`, com acesso só a este repositório e permissão **Actions: Read and write** — sem essa permissão marcada, a API devolve `403 Resource not accessible by integration` (ou às vezes um `404` enganoso, que parece "não achei o repo" mas na real é permissão faltando). Esse token tem validade (coloquei 1 ano) — precisa renovar antes de vencer.
2. Uma **conta no cron-job.org** com uma **API key** gerada em Console → Settings → API.
3. Os 4 jobs configurados lá dentro, um por workflow, cada um com o `Authorization: Bearer <token>` no header e o corpo `{"ref":"Nomain"}`.

**Duas pegadinhas que me pegaram na hora de configurar via API deles**, deixando registrado pra não cair de novo:
- O `Content-Type` da chamada pra API do cron-job.org tem que ser **exatamente** `application/json` — se vier com `; charset=utf-8` no final, a API deles trata o corpo como vazio e devolve `400`.
- A API deles tem rate limit de **1 requisição/segundo** (5/minuto) pra criar job — se mandar tudo de uma vez, os jobs seguintes voltam com `429 Too Many Requests`.

Pra mudar um horário: entro direto no painel do cron-job.org (`cron-job.org/en/members/jobs/`), edito o job, e pronto — não precisa mexer em nada aqui no repositório.

### 7. Aviso no WhatsApp quando alguma automação falha

Antes disso eu só descobria que algo tinha quebrado se entrasse manualmente no GitHub Actions ou percebesse que um relatório não chegou no Drive. Agora, se um dos 4 workflows falhar depois de esgotar todas as tentativas, chega um aviso direto no meu WhatsApp — em qualquer horário, inclusive numa falha do Tableau às 15h, não só na primeira execução do dia.

Uso o **CallMeBot**, que é grátis mas só serve pra mandar mensagem pra mim mesmo (não dá — e nem devia — pra usar isso pra avisar cliente). Configuração:

1. Adicionei o número deles nos meus contatos (o número certo muda de vez em quando, então sempre confiro em [callmebot.com/whatsapp](https://www.callmebot.com/whatsapp/) antes de ativar de novo).
2. Mandei pra esse contato, pelo WhatsApp: `I allow callmebot to send me messages`.
3. Em menos de 2 minutos o bot respondeu com a minha apikey.
4. Cadastrei `CALLMEBOT_PHONE` (meu número, com código do país, sem `+`) e `CALLMEBOT_APIKEY` (a chave que recebi) como Secrets do repositório.

Cada workflow tem um passo `Notificar falha no WhatsApp` (`if: failure()`) no final, que roda quando a automação falha de vez.

Se algum dia eu quiser trocar o WhatsApp por e-mail/Telegram/Slack, é só trocar esses passos em cada `.yml` — o resto do workflow não muda.

**Pegadinha que me pegou na hora de ativar**: o `CALLMEBOT_PHONE` precisa ser **exatamente** o número que mandou a mensagem de ativação pro bot — mesma quantidade de dígitos, sem um `9` a mais nem a menos. Se o número no secret não bater direitinho com o que o CallMeBot tem cadastrado pra aquela apikey, ele responde `APIKey is invalid` mesmo com a apikey certa (a mensagem de erro engana, parece problema na apikey, mas era o telefone). Testei end-to-end forçando uma falha proposital numa branch descartável e só validei o `CALLMEBOT_APIKEY` como certo depois de ajustar o número — se acontecer nível "chega no log como sucesso mas não chega no WhatsApp", o primeiro lugar a olhar é a resposta que o CallMeBot devolve (dá pra adicionar um `echo` temporário no passo pra ver o corpo da resposta, foi assim que descobri).

**Segunda pegadinha, essa depois de um tempo sem uso**: o CallMeBot pausa a conta sozinho "due to technical issues" depois de um período de inatividade — o workflow continua terminando com sucesso (a chamada HTTP responde 200), mas o corpo da resposta é uma página HTML dizendo `Your Account is Paused` em vez de confirmar o envio, e a mensagem não chega no WhatsApp. Não dá pra saber isso só pelo "✅" do GitHub Actions, só lendo o log do passo. Resolve mandando a palavra **`resume`** pro número do bot no WhatsApp (o número certo está sempre em [callmebot.com/whatsapp](https://www.callmebot.com/whatsapp/), pode mudar).

Se um dia eu quiser voltar a usar só o `schedule:` do GitHub (por exemplo, se abandonar o cron-job.org), é só descomentar o bloco no `.yml` correspondente e desativar o job lá no painel deles, pra não disparar duas vezes.

### 8. Resumo diário no WhatsApp (em vez de um aviso por execução)

No começo, cada workflow mandava seu próprio "✅ sucesso" na hora — mas isso virava 3-4 mensagens separadas todo dia (mais a do Tableau). Troquei por **um resumo único de manhã**, com a contagem de linhas importadas nas 3 bases do PBI.

Como funciona:

1. Em vez de mandar WhatsApp direto, cada um dos 4 workflows grava o resultado (sucesso/falha) num arquivo `status/hoje.json` no próprio repositório, usando `scripts/atualizar_status.py` — e dá commit nisso automaticamente (`scripts/commit_status.sh`). Se a data no arquivo for de ontem, ele reseta sozinho antes de gravar, então não precisa de nenhum passo separado pra "zerar o dia".
   - O PBI também grava a quantidade de linhas de cada base (Inadimplência, Relacionamento, Vendas) — o `pbi_export.py` conta isso automaticamente depois de completar as 3 importações e salva num `contagens.json` temporário, que o workflow lê e junta ao status.
   - O Tableau só grava status na **1ª execução do dia (08h BRT)** — nas outras 10 execuções horárias ele confere a hora e pula, pra não sobrescrever à toa o campo "1ª execução" com resultados do meio do dia.
2. Um **5º workflow, `resumo-diario.yml`**, disparado 1x por dia às **09:00 BRT** (depois que as 4 automações diárias já rodaram) por mais um job no cron-job.org, lê `status/hoje.json` e manda a mensagem consolidada via `scripts/enviar_resumo_diario.py`. Fica mais ou menos assim:

   ```
   📊 Resumo do dia 17-08-2026
   Gerar Perfil: ✅
   EVO Inadimplentes: ✅
   PBI Export: ✅
     • Inadimplência: 1234
     • Relacionamento: 567
     • Vendas: 890
   Tableau (1ª execução): ✅

   Total: 4/4 OK
   ```

   Automação que ainda não rodou naquele dia (ex: Gerar Perfil no fim de semana, já que só roda seg-sex) aparece como "⏳ não rodou" e não entra no total.

O aviso de **falha continua imediato**, sem passar pelo resumo — se algo quebrar às 10h da manhã eu quero saber na hora, não esperar o resumo do dia seguinte.

Pra esse 5º job funcionar, precisei dar permissão de escrita pro `GITHUB_TOKEN` automático de cada workflow (`permissions: contents: write` no topo do `.yml`) — sem isso o `git push` do status falha. Como em teoria dois workflows podem terminar quase juntos e tentar commitar ao mesmo tempo, `commit_status.sh` tenta de novo (com `git pull --rebase`) até 3 vezes antes de desistir — nesse caso raríssimo, o campo daquela automação simplesmente não aparece no resumo daquele dia, mas o resto continua funcionando.

### 9. Por que o repositório é público

**O problema**: repositório privado + 4 automações com navegador (destaque pro Tableau, de hora em hora) estourou a cota gratuita de minutos do GitHub Actions em poucos dias — o runner `ubuntu-latest` cobra por minuto em repositório privado, e eu não queria pagar por isso.

**Caminhos considerados e por que foram descartados:**

- **Runner self-hosted numa VM gratuita** (Oracle Cloud Always Free): cheguei a documentar o passo a passo inteiro pra isso, mas travou logo no cadastro — a Oracle exige cartão de crédito físico pra validar a conta e **rejeita explicitamente** cartão de débito, virtual ou pré-pago (inclusive Nubank, que muita gente tenta). Sem cartão de crédito, não dá pra criar a conta.
- **Outras nuvens grátis** (Google Cloud, AWS, Azure): todas pedem cartão também pra verificação antifraude — não resolve o mesmo problema.
- **VPS "grátis pra sempre" sem cartão** (existem vários anunciados por aí): descartados por confiabilidade — são hospedagens de baixíssima procedência pra rodar login de sistema de cobrança com dado de cliente.
- **Deixar meu próprio PC ligado 24h como runner**: funcionaria, mas não quis depender disso.

**A solução sem custo e sem cartão**: tornar o repositório **público**. Actions em repositório público é do próprio GitHub, ilimitado e gratuito de verdade, sem pegadinha e sem prazo — só exigiu dois ajustes antes de virar a chave:

1. **Remover dos artefatos de execução tudo que tem dado pessoal de cliente.** Os relatórios de `evo-inadimplentes`, `pbi-export-redeservice` e `tableau-agendamentos` (CPF, nome, dívida, agendamento de clientes reais) e o diagnóstico de erro do PBI (screenshot + HTML da tela do RedeService) pararam de subir como artefato — em repo público, artefato é baixável por qualquer pessoa. Os relatórios continuam indo pro Google Drive normalmente, que já era o destino oficial; só o "backup extra" via artefato do GitHub é que saiu.
2. **Os Secrets continuam privados independente da visibilidade do repositório** — isso nunca foi um problema; GitHub Secrets não ficam visíveis em repositório público nem em log nenhum. O risco era só os artefatos e o histórico do git (ver abaixo).

**Um detalhe que fica registrado**: o histórico antigo do git (de antes dessa mudança) tem uma senha do RedeService exposta num README antigo, de quando o repositório ainda era privado — decidiu-se aceitar esse risco em vez de reescrever o histórico. Se algum dia precisar reforçar isso, o caminho é trocar a senha no RedeService e reescrever o histórico do git antes de mexer em mais nada.
