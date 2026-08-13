# Tableau — Relatório de Agendamentos (AmorSaúde)

Faz login no Tableau Online, abre o relatório de Agendamentos, preenche o período (1º ao último dia do mês) e exporta o crosstab para o Google Drive.

## Secrets necessários

| Secret | Valor |
|---|---|
| `TABLEAU_EMAIL` | e-mail de login do Tableau |
| `TABLEAU_SENHA` | senha do Tableau |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON da conta de serviço do Google (opcional, para upload no Drive) |
| `GDRIVE_FOLDER_TABLEAU_ID` | ID da pasta "Agendamentos" no Drive (opcional) |

## ⚠️ Ponto de atenção — Login Microsoft/MFA

O login passa pela tela de autenticação da Microsoft (Azure AD). Se a conta tiver MFA ativo, a automação trava em modo headless no GitHub Actions (não há como responder ao código MFA automaticamente). Veja o README da raiz para orientações.

## Parâmetros

O script aceita os mesmos argumentos da versão original:

```bash
python tableau_agendamentos.py --mes 8 --ano 2026 --headless
```

Sem `--mes`/`--ano`, usa o mês/ano atual. No workflow do GitHub Actions ele roda sempre com `--headless` (obrigatório, já que não há tela no runner).

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
playwright install chromium
TABLEAU_EMAIL=... TABLEAU_SENHA=... python tableau_agendamentos.py
```

## Workflow

`.github/workflows/tableau-agendamentos.yml` — roda **de hora em hora (minuto :12), das 08h às 18h, de segunda a sábado (Brasília)**, igual ao `Controlador.py` original: ele não faz uma extração única, e sim mantém o relatório sempre atualizado ao longo do expediente. O minuto `:12` (em vez de `:00` em ponto) evita o horário de maior fila/atraso do agendador do GitHub Actions — veja o README da raiz. Cada execução baixa o relatório do mês atual e sobrescreve, direto na pasta de destino no Drive (sem subpasta por data), o mesmo arquivo `Agendamentos.csv` das execuções anteriores — nunca cria um arquivo novo. Em caso de falha, tenta novamente até 3 vezes com 1 minuto de espera entre tentativas.

Pode ser disparado manualmente em **Actions → Tableau - Relatorio de Agendamentos → Run workflow** (nesse caso ele roda com o mês/ano atuais, já que o `workflow_dispatch` não tem campos de input configurados — se quiser rodar para um mês específico manualmente, ajuste o `run:` do workflow temporariamente ou rode localmente).

> Isso equivale a ~66 execuções por semana. Se isso for mais frequente do que o necessário (por exemplo, se bastasse rodar só 1x por dia), me avise que eu reduzo a frequência no `cron`.
