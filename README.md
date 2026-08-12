# AS Consultoria — Automações

Repositório com as automações web (Playwright/Selenium) que rodam **automaticamente pelo GitHub Actions**, uma pasta por automação:

| Pasta | O que faz | Sistema | Frequência (baseada nos 4 controladores enviados) |
|---|---|---|---|
| [`gerar-perfil-redeservice/`](gerar-perfil-redeservice) | Dispara a "Geração de Perfil" no RedeService | RedeService (Cartão de Todos) | segunda a sexta, 08:30 (BRT) |
| [`evo-inadimplentes/`](evo-inadimplentes) | Extrai clientes inadimplentes (Salvador + Pernambués) | EVO / AllpFit | todos os dias, 07:00 (BRT) |
| [`pbi-export-redeservice/`](pbi-export-redeservice) | Exporta 3 relatórios do Power BI e reimporta no RedeService | Power BI + RedeService | todos os dias, 07:40 (BRT) |
| [`tableau-agendamentos/`](tableau-agendamentos) | Exporta relatório de agendamentos do mês corrente | Tableau (AmorSaúde) | **de hora em hora, 08h às 18h**, segunda a sábado (BRT) |

Esses horários vieram dos 4 controladores que você me passou (`ControladorGerarPerfil.py`, `ControladorEVO.py`, `ControladorPBI.py`, `Controlador.py`) e já estão configurados nos 4 arquivos em `.github/workflows/`. Se algum horário mudar, é só me avisar.

> **Atenção — Tableau roda 11x por dia.** O `Controlador.py` original não faz uma extração única por mês: ele reexecuta o script **toda hora cheia** dentro do expediente (08h-18h, seg-sáb) para manter o relatório sempre atualizado. Reproduzi esse comportamento no workflow, mas isso significa ~66 execuções de navegador por semana só dessa automação. Se sua conta do GitHub tiver um limite de minutos de Actions (planos gratuitos/Pro de repositórios privados têm cota mensal), vale ficar de olho no consumo em **Settings → Billing → Actions** nas primeiras semanas.

## O que mudou em relação aos scripts originais

Os scripts originais foram feitos para rodar no seu computador (Windows, com Google Drive Desktop mapeado como unidade `G:\` e, num caso, o Microsoft Excel instalado). Isso não existe num runner do GitHub Actions (uma máquina Linux efêmera na nuvem). Por isso, cada script foi adaptado:

1. **Sem senha no código.** Todo login/senha agora vem de variáveis de ambiente, preenchidas a partir de **GitHub Secrets** (nunca aparecem no código-fonte nem nos logs).
2. **Sem `G:\...` (Google Drive Desktop).** Os arquivos baixados são salvos numa pasta temporária local (dentro do runner) e depois enviados à mesma estrutura de pastas do Drive via **Google Drive API** (conta de serviço). Se o upload falhar por qualquer motivo, o arquivo não se perde: ele também fica disponível para download manual na aba **Actions → (execução) → Artifacts** do GitHub por alguns dias.
3. **Sem Excel/`win32com`** (só no `pbi-export-redeservice`). A conversão de `.xlsx` para `.csv` que dependia de abrir o Excel de verdade foi reescrita usando só `openpyxl`, sem precisar do Office instalado.

## Passo a passo geral de configuração

### 1. Criar a conta de serviço do Google (para o upload no Drive)

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/) e crie (ou use) um projeto.
2. Ative a **Google Drive API** em "APIs e serviços" → "Biblioteca".
3. Vá em "APIs e serviços" → "Credenciais" → "Criar credenciais" → **Conta de serviço**. Dê um nome (ex: `automacoes-drive`) e finalize.
4. Abra a conta de serviço criada → aba "Chaves" → "Adicionar chave" → **Criar nova chave** → tipo **JSON**. Um arquivo `.json` será baixado — guarde-o, ele será colado inteiro num Secret do GitHub (passo 2).
5. Copie o **e-mail da conta de serviço** (algo como `automacoes-drive@SEU-PROJETO.iam.gserviceaccount.com`).
6. **Contas de serviço não têm cota de armazenamento própria** — confirmado na prática: tentar enviar arquivo pra uma pasta comum do "Meu Drive" (mesmo compartilhada como Editor) falha com `storageQuotaExceeded`. Escolhemos resolver mantendo as pastas onde já estão, usando **Delegação em todo o domínio** (Domain-wide Delegation) — a conta de serviço passa a agir "como se fosse" um usuário real do Workspace, usando a cota dele:
   - No Cloud Console, abra a conta de serviço → **Detalhes avançados** → ative **"Ativar a Delegação em todo o domínio Google Workspace"** (se ainda não estiver) → anote o **ID do cliente** (um número, diferente do e-mail).
   - No [Admin Console do Workspace](https://admin.google.com/) (precisa ser administrador): **Segurança → Controles de acesso e dados → Controles de API → Delegação em todo o domínio** → **Adicionar novo**.
     - **ID do cliente**: o número que você anotou.
     - **Escopos OAuth**: `https://www.googleapis.com/auth/drive`
     - Autorizar.
   - Isso dá à conta de serviço acesso a **todo o Drive** do usuário que ela passar a representar — escolha um usuário cuja conta já tenha acesso natural às pastas de destino (idealmente uma conta de uso interno/operacional, não a conta pessoal principal de alguém).
7. Pegue o **ID de cada pasta de destino** (Relatórios EVO, Relatorios PBI, Agendamentos), sem precisar mover nada: abra a pasta no navegador e copie o trecho final da URL, depois de `folders/`.
   `https://drive.google.com/drive/folders/1AbCdEfGhIjKlmNoPQRstuVWxyz` → o ID é `1AbCdEfGhIjKlmNoPQRstuVWxyz`.

   > Alternativa mais simples de configurar (mas exige mover as pastas): criar uma **Drive Compartilhada** e adicionar a conta de serviço como membro dela. O código já suporta os dois jeitos — se `GDRIVE_IMPERSONATE_USER` (próximo passo) não for definido, ele tenta a conta de serviço diretamente, o que só funciona em Drives Compartilhadas.

### 2. Cadastrar os Secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie estes secrets:

| Secret | Usado por | Valor |
|---|---|---|
| `RS_LOGIN` | Gerar Perfil, PBI Export | usuário do RedeService (ex: `2`) |
| `RS_SENHA` | Gerar Perfil, PBI Export | senha do RedeService |
| `EVO_LOGIN` | EVO Inadimplentes | e-mail de login do EVO |
| `EVO_SENHA` | EVO Inadimplentes | senha do EVO |
| `PBI_LOGIN_EMAIL` | PBI Export | e-mail de login do Power BI |
| `PBI_SENHA` | PBI Export | senha do Power BI |
| `TABLEAU_EMAIL` | Tableau Agendamentos | e-mail de login do Tableau |
| `TABLEAU_SENHA` | Tableau Agendamentos | senha do Tableau |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | EVO, PBI Export, Tableau | **conteúdo inteiro** do arquivo `.json` baixado no passo 1.4 (cole o JSON completo) |
| `GDRIVE_FOLDER_EVO_ID` | EVO Inadimplentes | ID da pasta "Relatórios EVO" no Drive |
| `GDRIVE_FOLDER_PBI_ID` | PBI Export | ID da pasta "Relatorios PBI" no Drive |
| `GDRIVE_FOLDER_TABLEAU_ID` | Tableau Agendamentos | ID da pasta "Agendamentos" no Drive |
| `GDRIVE_IMPERSONATE_USER` | EVO, PBI Export, Tableau | e-mail do usuário Workspace que a conta de serviço vai representar (Delegação em todo o domínio) |

Todas as senhas acima estavam em texto puro nos scripts originais — foram trocadas por essa variável de ambiente e **não existem mais em nenhum arquivo do repositório**.

### 3. Horário (cron) de cada automação

Os 4 workflows em `.github/workflows/*.yml` já estão configurados com os horários dos controladores originais (tabela acima). O cron do GitHub Actions é **sempre em UTC**, e o horário de Brasília é UTC-3 (sem horário de verão atualmente) — por isso cada `cron:` no `.yml` tem um comentário explicando a conversão feita.

Se algum horário mudar no futuro, é só editar a linha `cron:` do workflow correspondente. Fórmula rápida: `hora_UTC = hora_Brasília + 3`. Formato do cron: `minuto hora dia-do-mês mês dia-da-semana` (dia-da-semana: `1-5` = segunda a sexta, `1-6` = segunda a sábado, `*` = todo dia).

Cada workflow também reproduz a **lógica de retentativa** do respectivo controlador (número de tentativas e tempo de espera entre elas) — se a execução falhar, ele tenta de novo automaticamente antes de desistir e esperar o próximo ciclo agendado.

### 4. Testar manualmente antes de confiar no agendamento

Em cada workflow, na aba **Actions** do GitHub, escolha o workflow → **Run workflow** (botão à direita) para disparar uma execução manual (`workflow_dispatch`) sem esperar o horário agendado. Isso é essencial para validar login, seletores e o upload no Drive antes de deixar rodando sozinho.

### 5. Ressalvas importantes por automação

- **`pbi-export-redeservice`**: a conversão de Excel para CSV foi refeita sem o Excel. Mantive o delimitador `;` (ponto e vírgula) e encoding `utf-8-sig`, replicando o padrão regional do Excel em pt-BR — mas **confira o primeiro arquivo gerado** para garantir que o RedeService aceita esse formato na importação. Se der erro de layout na importação, o mais provável é precisar ajustar `CSV_DELIMITER`/`CSV_ENCODING` no topo de `pbi_export.py`.
- **`pbi-export-redeservice`** e **`tableau-agendamentos`**: os logins passam pela tela da Microsoft (Azure AD). Se a conta usada tiver **MFA (autenticação multifator)** ativo, a automação vai travar no GitHub Actions (não há como responder ao código MFA num runner headless). Se isso acontecer, peça ao administrador do Microsoft 365 para isentar essa conta específica de MFA, ou usar uma conta de serviço dedicada sem MFA para a automação.
- **`evo-inadimplentes`**: usa o canal `chrome` real do navegador (não o Chromium genérico) para reduzir detecção de automação — o workflow já instala isso via `playwright install --with-deps chrome`.

## Estrutura de cada pasta

Cada automação é independente: tem seu próprio script Python, `requirements.txt` e (quando precisa enviar arquivo ao Drive) `gdrive_utils.py`. Veja o README de cada pasta para detalhes específicos.
