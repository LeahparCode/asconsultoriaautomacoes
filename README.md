# AS Consultoria — Automações

Repositório com as automações web (Playwright/Selenium) que uso pra rodar os processos do dia a dia automaticamente pelo GitHub Actions, uma pasta por automação:

| Pasta | O que faz | Sistema | Horário (BRT) |
|---|---|---|---|
| [`gerar-perfil-redeservice/`](gerar-perfil-redeservice) | Dispara a "Geração de Perfil" no RedeService | RedeService (Cartão de Todos) | segunda a sexta, ~08:19 |
| [`evo-inadimplentes/`](evo-inadimplentes) | Extrai clientes inadimplentes (Salvador + Pernambués) | EVO / AllpFit | todos os dias, ~07:13 |
| [`pbi-export-redeservice/`](pbi-export-redeservice) | Exporta 3 relatórios do Power BI e reimporta no RedeService | Power BI + RedeService | todos os dias, ~07:53 |
| [`tableau-agendamentos/`](tableau-agendamentos) | Exporta relatório de agendamentos do mês corrente | Tableau (AmorSaúde) | **de hora em hora (minuto :29), 08h às 18h**, segunda a sábado |

Esses horários vieram dos controladores que eu já usava antes (`ControladorGerarPerfil.py`, `ControladorEVO.py`, `ControladorPBI.py`, `Controlador.py`) e estão configurados nos 4 arquivos em `.github/workflows/`.

> ⏸️ **Agendamento automático pausado.** Por enquanto os 4 workflows só rodam manualmente (`workflow_dispatch`) — comentei o bloco `schedule:` de cada um. O cron de cada horário continua documentado em comentário no próprio `.yml`, é só descomentar quando eu quiser voltar a rodar sozinho.

> **Sobre atraso no horário agendado.** O GitHub Actions **não garante** que um `schedule:` dispare no minuto exato — ele enfileira as execuções agendadas, e em momentos de pico (principalmente bem na hora cheia, `:00`) a fila fica maior e o atraso pode passar de 10-20 minutos. Isso é uma limitação da própria plataforma e não tem como ser eliminada 100% num plano gratuito/padrão de Actions. O que dá pra fazer — e já apliquei nos horários acima — é evitar minutos redondos e múltiplos de 5 (`:00`, `:05`, `:10`, `:15`...), que concentram o maior volume de workflows do GitHub inteiro disparando ao mesmo tempo; por isso cada horário ficou deslocado alguns minutos (ex: EVO não roda mais às 07:00 em ponto, e sim 07:13), mantendo a mesma intenção original. Se algum dia precisar de horário exato garantido, a alternativa é disparar manualmente (**Actions → workflow → Run workflow**) ou usar um agendador externo que chame a API do GitHub (`workflow_dispatch`/`repository_dispatch`).

> **Atenção — Tableau roda até 11x por dia.** O `Controlador.py` original não faz uma extração única por mês: ele reexecuta o script **toda hora cheia** dentro do expediente (08h-18h, seg-sáb) pra manter o relatório sempre atualizado, e reproduzi esse comportamento no workflow. Isso dá ~66 execuções de navegador por semana só dessa automação — se a conta do GitHub tiver limite de minutos de Actions (planos gratuitos/Pro de repositórios privados têm cota mensal), vale ficar de olho no consumo em **Settings → Billing → Actions**.

## O que mudou em relação aos scripts originais

Os scripts originais rodavam no meu computador (Windows, com Google Drive Desktop mapeado como unidade `G:\` e, num caso, o Microsoft Excel instalado). Isso não existe num runner do GitHub Actions (uma máquina Linux efêmera na nuvem), então adaptei cada script:

1. **Sem senha no código.** Todo login/senha vem de variáveis de ambiente, preenchidas a partir de **GitHub Secrets** (nunca aparecem no código-fonte nem nos logs).
2. **Sem `G:\...` (Google Drive Desktop).** Os arquivos baixados são salvos numa pasta temporária local (dentro do runner) e depois enviados à mesma estrutura de pastas do Drive via **Google Drive API**. Se o upload falhar por qualquer motivo, o arquivo não se perde: fica disponível pra download manual na aba **Actions → (execução) → Artifacts** do GitHub por alguns dias.
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

E, dependendo da opção escolhida no passo 1 pro upload no Drive:

| Secret | Opção | Valor |
|---|---|---|
| `GDRIVE_OAUTH_CLIENT_ID` | A — OAuth de usuário | Client ID gerado no Cloud Console |
| `GDRIVE_OAUTH_CLIENT_SECRET` | A — OAuth de usuário | Client secret gerado no Cloud Console |
| `GDRIVE_OAUTH_REFRESH_TOKEN` | A — OAuth de usuário | Impresso por `scripts/gerar_refresh_token_drive.py` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | B — Conta de serviço | **conteúdo inteiro** do arquivo `.json` da conta de serviço |
| `GDRIVE_IMPERSONATE_USER` | B — Conta de serviço + Delegação de domínio | e-mail do usuário Workspace representado (deixe sem definir se for usar Drive Compartilhada) |

Todas as senhas acima estavam em texto puro nos scripts originais — troquei por variável de ambiente e **não existem mais em nenhum arquivo do repositório**.

### 3. Horário (cron) de cada automação

Os 4 workflows em `.github/workflows/*.yml` estão configurados com os horários dos controladores originais (tabela lá em cima), mas **atualmente pausados** — só rodam manualmente até eu reativar. O cron do GitHub Actions é **sempre em UTC**, e o horário de Brasília é UTC-3 (sem horário de verão atualmente) — por isso cada `cron:` no `.yml` tem um comentário explicando a conversão feita.

Pra reativar um agendamento, é só descomentar o bloco `schedule:` no `.yml` correspondente (o cron já fica documentado no comentário). Pra mudar um horário, edito a linha `cron:`. Fórmula rápida: `hora_UTC = hora_Brasília + 3`. Formato do cron: `minuto hora dia-do-mês mês dia-da-semana` (dia-da-semana: `1-5` = segunda a sexta, `1-6` = segunda a sábado, `*` = todo dia).

Cada workflow também reproduz a **lógica de retentativa** do respectivo controlador (número de tentativas e tempo de espera entre elas) — se a execução falhar, ele tenta de novo automaticamente antes de desistir e esperar o próximo ciclo.

### 4. Testar manualmente antes de confiar no agendamento

Em cada workflow, na aba **Actions** do GitHub, escolho o workflow → **Run workflow** (botão à direita) pra disparar uma execução manual (`workflow_dispatch`) sem esperar o horário agendado. Isso é essencial pra validar login, seletores e o upload no Drive antes de deixar rodando sozinho.

### 5. Ressalvas importantes por automação

- **`pbi-export-redeservice`**: a conversão de Excel pra CSV foi refeita sem o Excel, usando delimitador `;` (ponto e vírgula), encoding `cp1252` (ANSI/Windows-1252) e datas/números formatados como o Excel real geraria (`DD/MM/AAAA`, decimal com vírgula), replicando o padrão do "Salvar como CSV" do Excel em pt-BR. **Atenção**: essa base já teve rejeições silenciosas do backend do RedeService (a tela de upload dizia "sucesso", mas o histórico de importação mostrava erro de SQL `LEFT`/`SUBSTRING`) — **sempre confiro o histórico de importação dentro do RedeService**, não só o log do script, pra confirmar que a importação realmente foi processada.
- **`pbi-export-redeservice`** e **`tableau-agendamentos`**: os logins passam pela tela da Microsoft (Azure AD). Se a conta usada tiver **MFA (autenticação multifator)** ativo, a automação trava no GitHub Actions (não dá pra responder ao código MFA num runner headless). Se acontecer, é preciso isentar essa conta de MFA no Microsoft 365 ou usar uma conta de serviço dedicada sem MFA.
- **`evo-inadimplentes`**: usa o canal `chrome` real do navegador (não o Chromium genérico) pra reduzir detecção de automação — o workflow já instala isso via `playwright install --with-deps chrome`.

## Estrutura de cada pasta

Cada automação é independente: tem seu próprio script Python, `requirements.txt` e (quando precisa enviar arquivo ao Drive) `gdrive_utils.py`. Veja o README de cada pasta pra detalhes específicos.
