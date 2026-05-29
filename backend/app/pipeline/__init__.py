"""Analysis pipeline: embeddings, topic modeling, time series and descriptions.

Each stage is defined behind a small interface with two kinds of implementations:

* an **offline fallback** (pure ``numpy`` / ``scikit-learn``) so the whole pipeline
  runs without API keys or heavy ML installs - ideal for tests and demos;
* a **scientific/production** implementation (Sentence-BERT, BERTopic, an LLM)
  enabled via configuration once the optional extras are installed.
"""
