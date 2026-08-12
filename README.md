# AS Consultoria — Automações

Repositório com as automações web (Playwright/Selenium) que rodam **automaticamente pelo GitHub Actions**, uma pasta por automação:

| Pasta | O que faz | Sistema | Frequência (provisória) |
|---|---|---|---|
| [`gerar-perfil-redeservice/`](gerar-perfil-redeservice) | Dispara a "Geração de Perfil" no RedeService | RedeService (Cartão de Todos) | dias úteis, 08:00 (BRT) |
| [`evo-inadimplentes/`](evo-inadimplentes) | Extrai clientes inadimplentes (Salvador + Pernambués) | EVO / AllpFit | diário, 08:00 (BRT) |
| [`pbi-export-redeservice/`](pbi-export-redeservice) | Exporta 3 relatórios do Power BI e reimporta no RedeService | Power BI + RedeService | dias úteis, 08:00 (BRT) |
| [`tableau-agendamentos/`](tableau-agendamentos) | Exporta relatório de agendamentos do mês | Tableau (AmorSaúde) | mensal, dia 1, 08:00 (BRT) |

Os horários acima estão **provisórios** — assim que você me passar o controlador com os horários reais de cada automação, eu ajusto o `cron` de cada workflow em `.github/workflows/`.

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
6. No Google Drive, entre em cada uma das 3 pastas de destino (Relatórios EVO, Relatorios PBI, Agendamentos) e **compartilhe a pasta** com esse e-mail, dando permissão de **Editor**.
7. Pegue o **ID da pasta** de cada uma: abra a pasta no navegador e copie o trecho final da URL, depois de `folders/`.
   `https://drive.google.com/drive/folders/1AbCdEfGhIjKlmNoPQRstuVWxyz` → o ID é `1AbCdEfGhIjKlmNoPQRstuVWxyz`.

   ⚠️ **Atenção — limitação conhecida:** se essas pastas forem do **Google Drive pessoal (Gmail comum)**, contas de serviço podem falhar ao criar arquivos ali (elas não têm cota de armazenamento própria fora de "Drives Compartilhados" do Google Workspace). O upload foi implementado para **nunca travar a automação** se isso acontecer — ele só avisa no log e segue em frente, já que o arquivo também fica salvo como artefato do Actions. Teste um upload manualmente (rodando o workflow via `workflow_dispatch`) para confirmar se funciona no seu caso; se não funcionar, me avise que ajustamos a estratégia (ex: OAuth de usuário em vez de conta de serviço).

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

Todas as senhas acima estavam em texto puro nos scripts originais — foram trocadas por essa variável de ambiente e **não existem mais em nenhum arquivo do repositório**.

### 3. Ajustar o horário (cron) de cada automação

Cada workflow em `.github/workflows/*.yml` tem uma linha `cron:` marcada com `# TODO`. O cron do GitHub Actions é **sempre em UTC**, e o horário de Brasília é UTC-3 (sem horário de verão atualmente). Fórmula rápida: `hora_UTC = hora_Brasília + 3`.

Exemplo: rodar às 07:30 (Brasília) → `30 10 * * *` (10:30 UTC).

Assim que você me mandar os horários do controlador, eu edito essas 4 linhas diretamente.

Formato do cron: `minuto hora dia-do-mês mês dia-da-semana` (dia-da-semana: `1-5` = segunda a sexta, `*` = todo dia).

### 4. Testar manualmente antes de confiar no agendamento

Em cada workflow, na aba **Actions** do GitHub, escolha o workflow → **Run workflow** (botão à direita) para disparar uma execução manual (`workflow_dispatch`) sem esperar o horário agendado. Isso é essencial para validar login, seletores e o upload no Drive antes de deixar rodando sozinho.

### 5. Ressalvas importantes por automação

- **`pbi-export-redeservice`**: a conversão de Excel para CSV foi refeita sem o Excel. Mantive o delimitador `;` (ponto e vírgula) e encoding `utf-8-sig`, replicando o padrão regional do Excel em pt-BR — mas **confira o primeiro arquivo gerado** para garantir que o RedeService aceita esse formato na importação. Se der erro de layout na importação, o mais provável é precisar ajustar `CSV_DELIMITER`/`CSV_ENCODING` no topo de `pbi_export.py`.
- **`pbi-export-redeservice`** e **`tableau-agendamentos`**: os logins passam pela tela da Microsoft (Azure AD). Se a conta usada tiver **MFA (autenticação multifator)** ativo, a automação vai travar no GitHub Actions (não há como responder ao código MFA num runner headless). Se isso acontecer, peça ao administrador do Microsoft 365 para isentar essa conta específica de MFA, ou usar uma conta de serviço dedicada sem MFA para a automação.
- **`evo-inadimplentes`**: usa o canal `chrome` real do navegador (não o Chromium genérico) para reduzir detecção de automação — o workflow já instala isso via `playwright install --with-deps chrome`.

## Estrutura de cada pasta

Cada automação é independente: tem seu próprio script Python, `requirements.txt` e (quando precisa enviar arquivo ao Drive) `gdrive_utils.py`. Veja o README de cada pasta para detalhes específicos.
