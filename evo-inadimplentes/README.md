# EVO (AllpFit) — Extração de Clientes Inadimplentes

Faz login no EVO, extrai a lista de clientes inadimplentes de duas unidades (Salvador e Salvador Pernambués) e envia os arquivos ao Google Drive.

## Secrets necessários

| Secret | Valor |
|---|---|
| `EVO_LOGIN` | e-mail de login do EVO |
| `EVO_SENHA` | senha do EVO |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | JSON da conta de serviço do Google (veja o README da raiz) |
| `GDRIVE_FOLDER_EVO_ID` | ID da pasta "Relatórios EVO" no Drive |

Se `GDRIVE_SERVICE_ACCOUNT_JSON`/`GDRIVE_FOLDER_EVO_ID` não estiverem configurados, o script continua funcionando normalmente — só não envia nada ao Drive. **Desde 19/08/2026 (repositório público) o arquivo não sobe mais como artefato do GitHub Actions** — é dado pessoal de cliente (CPF, nome, dívida), e artefato em repo público é baixável por qualquer pessoa. Sem o Drive configurado, o arquivo fica só no runner (efêmero).

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
playwright install chrome
EVO_LOGIN=seu@email.com EVO_SENHA=suasenha EVO_HEADLESS=false python script_evo.py
```

## Workflow

`.github/workflows/evo-inadimplentes.yml` — todo dia às ~07:13 (Brasília; deslocado alguns minutos da hora cheia pra sofrer menos atraso de fila do agendador do GitHub, veja o README da raiz), igual ao `ControladorEVO.py` original. Em caso de falha, tenta novamente até 5 vezes com 5 minutos de espera entre tentativas. Pode ser disparado manualmente em **Actions → EVO AllpFit - Inadimplentes → Run workflow**.

Os arquivos gerados vão pra uma subpasta com a data do dia dentro da pasta de destino no Drive (uma subpasta nova por dia) — se a extração rodar de novo no mesmo dia, o arquivo já existente na subpasta daquele dia é substituído em vez de duplicado. Screenshots de erro (`erro_evo_*.png`, sem dado de cliente) continuam subindo como artefato da execução em caso de falha.
