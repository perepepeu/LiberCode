# Provider System

LiberCode supports multiple AI providers through a unified interface. Each provider implements the `BaseProvider` abstract class and can be swapped at runtime.

## Available Providers

| Provider | Env Variable | Default Model | Install Command |
|----------|-------------|---------------|-----------------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o | `pip install openai` |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-5 | `pip install anthropic` |
| Google | `GOOGLE_API_KEY` | gemini-2.0-flash | `pip install google-generativeai` |
| Groq | `GROQ_API_KEY` | llama-3.3-70b-versatile | `pip install groq` |
| OpenRouter | `OPENROUTER_API_KEY` | anthropic/claude-sonnet-4-5 | `pip install openai httpx` |
| Ollama | *(none needed)* | llama3.2 | `pip install openai` |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | `pip install openai` |
| Together | `TOGETHER_API_KEY` | meta-llama/Llama-3.3-70B-Instruct-Turbo | `pip install openai` |
| Builtin | *(none needed)* | Qwen2.5-Coder-7B-Instruct | *(included)* |
| Custom | *(user-provided)* | *(user-provided)* | *(included)* |

## /provider Command

### List all providers
```
/provider
/provider list
```

### Switch provider directly
```
/provider openai
/provider openai gpt-4o-mini
/provider anthropic claude-sonnet-4-5
```

### Interactive setup wizard
```
/provider setup
```

## config.yaml Example

```yaml
provider:
  name: openai
  model: gpt-4o

providers:
  openai:
    name: openai
    api_key: sk-...
    model: gpt-4o
  anthropic:
    name: anthropic
    api_key: sk-ant-...
    model: claude-sonnet-4-5
  groq:
    name: groq
    api_key: gsk_...
```

## Environment Variables

Set the appropriate environment variable for your provider. Config file values take priority over environment variables.

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
export GROQ_API_KEY="gsk_..."
export OPENROUTER_API_KEY="..."
export DEEPSEEK_API_KEY="..."
export TOGETHER_API_KEY="..."
```

## Runtime Provider Swap

```python
from libercode.providers.registry import build_provider
from libercode.providers.base import ProviderError

try:
    provider = build_provider("openai", api_key="sk-...", model="gpt-4o")
except ProviderError as e:
    print(f"Failed: {e}")
```

## Optional Dependencies

```bash
pip install libercode[openai]     # OpenAI
pip install libercode[anthropic]  # Anthropic
pip install libercode[google]     # Google
pip install libercode[groq]       # Groq
pip install libercode[all]        # All providers
```
