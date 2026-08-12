# Gerar Perfil — RedeService

Abre o RedeService, navega em "Processos Diários" → "Geração de Perfil", clica em "Novo", marca "Selecionar todos" e clica em "Iniciar".

Não gera nem salva nenhum arquivo — é só um clique de sistema, então não depende de Google Drive.

## Secrets necessários

| Secret | Valor |
|---|---|
| `RS_LOGIN` | usuário do RedeService |
| `RS_SENHA` | senha do RedeService |

## Rodar localmente (opcional, para testar)

```bash
pip install -r requirements.txt
playwright install chromium
RS_LOGIN=2 RS_SENHA=Admin@2026 python gerar_perfil.py
```

## Workflow

`.github/workflows/gerar-perfil.yml` — cron provisório: dias úteis às 08:00 (Brasília). Pode ser disparado manualmente em **Actions → Gerar Perfil - RedeService → Run workflow**.

Em caso de erro, um screenshot (`erro_geracao_perfil.png`) sobe como artefato da execução.
