---
description: 'agent-clicker — Архитектура: LLM factory (ChatOpenAI). Загружать при работе с llm/.'
applyTo: '**/llm/**'
---
# agent-clicker — Архитектура проекта

## 8. LLM

### 8.1 `llm/factory.py`

`build_llm(agent: AgentSettings, static: Settings)` → `ChatOpenAI`: создаёт langchain `ChatOpenAI` с model/api_key/base_url из настроек. Смена модели — только через `AgentSettings.llm_model`. Никаких других LLM-провайдеров.
