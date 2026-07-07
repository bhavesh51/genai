# Project 3 — LLM Fine-tuning Pipeline on RHOAI

QLoRA/SFT fine-tuning pipeline using RHOAI Data Science Pipelines (Kubeflow Pipelines v2).

## Stack
- **Training**: QLoRA via PEFT + HuggingFace Transformers
- **Distributed**: PyTorchJob (multi-GPU, multi-node)
- **Pipeline**: Kubeflow Pipelines v2 (Elyra compatible)
- **Evaluation**: lm-evaluation-harness (MMLU, TruthfulQA)
- **Registry**: RHOAI Model Registry

## Quick Start
```bash
cd projects/03-llm-finetuning-pipeline
pip install -r requirements.txt
# Submit pipeline to RHOAI
python pipelines/submit_pipeline.py --experiment my-experiment --run-name run-001
```

## Deploy on RHOAI
```bash
oc apply -k deploy/kustomize/overlays/production
```
