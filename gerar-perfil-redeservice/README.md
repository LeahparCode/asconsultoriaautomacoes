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
RS_LOGIN=seu_usuario RS_SENHA=sua_senha python gerar_perfil.py
```

## Workflow

`.github/workflows/gerar-perfil.yml` — segunda a sexta às ~08:23 (Brasília; deslocado alguns minutos da hora cheia pra sofrer menos atraso de fila do agendador do GitHub, veja o README da raiz), igual ao `ControladorGerarPerfil.py` original. Em caso de falha, tenta novamente até 3 vezes com 5 minutos de espera entre tentativas. Pode ser disparado manualmente em **Actions → Gerar Perfil - RedeService → Run workflow**.

Em caso de erro, um screenshot (`erro_geracao_perfil.png`) sobe como artefato da execução.
