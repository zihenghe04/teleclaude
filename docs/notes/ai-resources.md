## Overview

A curated collection of high-quality resources for learning about AI, large language models, and practical AI development. Updated as new resources are discovered.

## Foundational Concepts

### Understanding Transformers

The transformer architecture is the backbone of modern LLMs. Key resources:

- **"Attention Is All You Need"** — The original 2017 paper that introduced the transformer architecture
- **"The Illustrated Transformer"** by Jay Alammar — The best visual explanation of how transformers work
- **3Blue1Brown's neural network series** — Excellent visual intuition for deep learning fundamentals

### How LLMs Work

- **"What are LLMs?"** — Start with understanding tokenization, embedding, and next-token prediction
- **Scaling laws** — Why larger models with more data tend to perform better (Chinchilla, Kaplan et al.)
- **In-context learning** — How models learn from examples in the prompt without weight updates

## Prompt Engineering

### Core Techniques

| Technique | Description | When to Use |
|-----------|-------------|-------------|
| Zero-shot | Direct instruction, no examples | Simple, well-defined tasks |
| Few-shot | Provide 2-5 examples | When output format matters |
| Chain-of-Thought | "Think step by step" | Reasoning and math problems |
| Role prompting | "You are a senior engineer..." | Domain-specific tasks |
| Structured output | Request JSON/XML format | Data extraction, APIs |

### Tips for Better Prompts

1. **Be specific** — "Summarize in 3 bullet points" beats "Summarize this"
2. **Provide context** — Tell the model what it needs to know
3. **Show, don't tell** — Examples are more effective than lengthy instructions
4. **Iterate** — Treat prompting as an iterative refinement process

## Building with LLM APIs

### Architecture Patterns

```
User Input → Preprocessing → LLM API → Post-processing → Response
                  ↑                           ↓
              Context                    Validation
            (RAG, history)            (safety, format)
```

### Key Concepts

- **Temperature** — Controls randomness (0 = deterministic, 1 = creative)
- **Token limits** — Manage context window carefully; prompt caching can reduce costs
- **Streaming** — Use SSE/streaming for better UX in chat applications
- **Tool use / Function calling** — Let the model invoke structured functions

### Cost Optimization

> "The most expensive API call is the one you didn't need to make."

- Cache responses for identical or similar queries
- Use smaller models for simple tasks (routing, classification)
- Batch requests when real-time response isn't needed
- Use prompt caching for repeated system prompts

## AI Development Tools

### Essential Libraries

- **LangChain / LlamaIndex** — Frameworks for building LLM applications
- **Anthropic SDK / OpenAI SDK** — Official client libraries
- **Hugging Face Transformers** — For running open-source models locally

### Local Development

```bash
# Run open-source models locally
# Great for experimentation and privacy-sensitive use cases
ollama run llama3
```

## Evaluation and Testing

- **Define clear metrics** — Accuracy, relevance, safety, latency
- **Build eval datasets** — Curate examples of expected input/output pairs
- **Automated testing** — Use LLMs to evaluate LLM outputs (LLM-as-judge)
- **Human evaluation** — Essential for subjective quality assessment

## Ethics and Safety

- Understand model limitations and hallucination risks
- Implement content filtering and safety guardrails
- Be transparent about AI-generated content
- Consider bias in training data and outputs
- Respect data privacy and usage terms

## Staying Current

The AI field moves incredibly fast. Strategies for keeping up:

- Follow key researchers and practitioners on social media
- Read weekly newsletters (e.g., "The Batch" by Andrew Ng)
- Join communities (Hugging Face, Reddit r/MachineLearning)
- Build projects — hands-on experience is the best teacher
