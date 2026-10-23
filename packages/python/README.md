# ag-pii-vault

PII tokenization for LLM pipelines.

Detects personal data (names, emails, phone numbers and other Presidio entities), replaces it with deterministic HMAC tokens before text is sent to an LLM, and restores it in the response. Token mappings live in a local SQLite vault or in the hosted vault.

## Install

```sh
pip install "ag-pii-vault[all]"
npm install ag-pii-vault
```

Extras: `openai`, `anthropic`, `all`. Detection uses the spaCy model `en_core_web_lg`: `python -m spacy download en_core_web_lg`.

## Usage

```python
from ag_pii_vault import Detector, LocalVault, Tokenizer

detector = Detector()
tokenizer = Tokenizer(vault=LocalVault(path=":memory:"), key="my-hmac-secret")

text = "Contact John Smith at john@acme.com"
safe = tokenizer.tokenize(text, detector.analyze(text))
print(safe)                        # PII replaced by tokens
print(tokenizer.dehydrate(safe))   # original text restored
```

Output:

```
Contact PERSON_353fcd26 at EMAIL_9abc0eb1
Contact John Smith at john@acme.com
```

`SafeOpenAI` and `SafeAnthropic` wrap the official clients: messages are tokenized on the way out and restored on the way back.

The TypeScript package `ag-pii-vault` is a port of the core classes.

## Hosted API

`HostedVault` stores the token mappings in the hosted API instead of local SQLite. Pass `hosted_api_key="ag_live_..."` to `SafeOpenAI` or `SafeAnthropic`. API keys are issued at https://ai.artifact-network.org. The default endpoint is `https://ai-api.artifact-network.org`; pass a different base URL to use your own deployment.

## Development

```sh
cd packages/python && pip install -e ".[all]" && pytest
cd packages/typescript && npm ci && npm test
```

## License

MIT, Copyright (c) 2026 Adnan Ghribi.
