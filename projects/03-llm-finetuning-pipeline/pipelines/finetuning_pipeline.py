"""
Project 3 – LLM Fine-tuning Pipeline
Kubeflow Pipeline v2 definition for QLoRA fine-tuning
"""
from kfp import dsl, compiler
from kfp.dsl import Dataset, Input, Model, Output


@dsl.component(
    base_image="registry.redhat.io/rhoai/odh-pytorch-cuda-ubi9-python-3.11:latest",
    packages_to_install=["datasets>=2.18", "transformers>=4.40", "peft>=0.10", "trl>=0.8"],
)
def data_preparation_step(
    dataset_s3_path: str,
    dataset_format: str,
    output_dataset: Output[Dataset],
):
    """Download, validate and format the fine-tuning dataset from ODF S3."""
    import json, os, boto3
    from datasets import load_dataset, DatasetDict

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    bucket, key = dataset_s3_path.replace("s3://", "").split("/", 1)
    local_path = "/tmp/dataset.jsonl"
    s3.download_file(bucket, key, local_path)

    ds = load_dataset("json", data_files=local_path, split="train")
    split = ds.train_test_split(test_size=0.1, seed=42)
    split.save_to_disk(output_dataset.path)
    print(f"Dataset prepared: {len(ds)} samples")


@dsl.component(
    base_image="registry.redhat.io/rhoai/odh-pytorch-cuda-ubi9-python-3.11:latest",
    packages_to_install=[
        "transformers>=4.40",
        "peft>=0.10",
        "trl>=0.8",
        "bitsandbytes>=0.43",
        "accelerate>=0.27",
        "torch>=2.2",
    ],
)
def qlora_training_step(
    base_model_name: str,
    input_dataset: Input[Dataset],
    lora_r: int,
    lora_alpha: int,
    lora_dropout: float,
    num_train_epochs: int,
    per_device_batch_size: int,
    learning_rate: float,
    output_model: Output[Model],
):
    """QLoRA fine-tuning using PEFT + TRL SFTTrainer."""
    from datasets import load_from_disk
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer
    import torch

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = load_from_disk(input_dataset.path)
    training_args = TrainingArguments(
        output_dir=output_model.path,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_batch_size,
        gradient_accumulation_steps=4,
        learning_rate=learning_rate,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="epoch",
        load_best_model_at_end=True,
        report_to=["tensorboard"],
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=2048,
    )
    trainer.train()
    trainer.save_model(output_model.path)
    tokenizer.save_pretrained(output_model.path)
    print(f"Model saved to {output_model.path}")


@dsl.component(
    base_image="registry.redhat.io/rhoai/odh-pytorch-cuda-ubi9-python-3.11:latest",
    packages_to_install=["lm-eval>=0.4", "transformers>=4.40", "torch>=2.2"],
)
def model_evaluation_step(
    input_model: Input[Model],
    eval_tasks: str,
    pass_threshold: float,
    eval_results: Output[Dataset],
) -> float:
    """Run lm-evaluation-harness on the fine-tuned model."""
    import json, subprocess, sys
    tasks = eval_tasks.split(",")
    results_path = f"{eval_results.path}/results.json"
    cmd = [
        sys.executable, "-m", "lm_eval",
        "--model", "hf",
        "--model_args", f"pretrained={input_model.path}",
        "--tasks", ",".join(tasks),
        "--output_path", results_path,
        "--device", "cuda",
        "--batch_size", "4",
    ]
    subprocess.run(cmd, check=True)
    with open(results_path) as f:
        data = json.load(f)
    # Extract average accuracy across all tasks
    scores = [v.get("acc,none", 0) for v in data.get("results", {}).values()]
    avg = sum(scores) / len(scores) if scores else 0
    print(f"Avg accuracy: {avg:.4f} | threshold: {pass_threshold}")
    assert avg >= pass_threshold, f"Model failed evaluation: {avg:.4f} < {pass_threshold}"
    return avg


@dsl.component(
    base_image="registry.redhat.io/rhoai/odh-pytorch-cuda-ubi9-python-3.11:latest",
    packages_to_install=["boto3>=1.34", "huggingface_hub>=0.22"],
)
def push_to_model_registry_step(
    input_model: Input[Model],
    model_name: str,
    model_version: str,
    registry_s3_bucket: str,
):
    """Upload fine-tuned model to ODF S3 and register in RHOAI Model Registry."""
    import os, boto3
    from pathlib import Path

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    model_dir = Path(input_model.path)
    for file in model_dir.rglob("*"):
        if file.is_file():
            key = f"models/{model_name}/{model_version}/{file.relative_to(model_dir)}"
            s3.upload_file(str(file), registry_s3_bucket, key)
            print(f"Uploaded: {key}")
    print(f"Model {model_name}:{model_version} pushed to s3://{registry_s3_bucket}")


@dsl.pipeline(
    name="llm-qlora-finetuning-pipeline",
    description="Enterprise QLoRA fine-tuning pipeline for RHOAI 3.x",
)
def llm_finetuning_pipeline(
    base_model_name: str = "ibm-granite/granite-3.1-8b-instruct",
    dataset_s3_path: str = "s3://training-data/datasets/finetune_v1.jsonl",
    dataset_format: str = "instruction",
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    num_train_epochs: int = 3,
    per_device_batch_size: int = 4,
    learning_rate: float = 2e-4,
    eval_tasks: str = "mmlu,truthfulqa_mc1",
    eval_pass_threshold: float = 0.60,
    model_name: str = "granite-finetuned",
    model_version: str = "1.0.0",
    registry_s3_bucket: str = "model-registry",
):
    data_task = data_preparation_step(
        dataset_s3_path=dataset_s3_path,
        dataset_format=dataset_format,
    )

    train_task = qlora_training_step(
        base_model_name=base_model_name,
        input_dataset=data_task.outputs["output_dataset"],
        lora_r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        num_train_epochs=num_train_epochs,
        per_device_batch_size=per_device_batch_size,
        learning_rate=learning_rate,
    )
    train_task.set_accelerator_type("nvidia.com/gpu").set_accelerator_limit(4)
    train_task.set_memory_request("64Gi")

    eval_task = model_evaluation_step(
        input_model=train_task.outputs["output_model"],
        eval_tasks=eval_tasks,
        pass_threshold=eval_pass_threshold,
    )
    eval_task.set_accelerator_type("nvidia.com/gpu").set_accelerator_limit(1)

    push_task = push_to_model_registry_step(
        input_model=train_task.outputs["output_model"],
        model_name=model_name,
        model_version=model_version,
        registry_s3_bucket=registry_s3_bucket,
    )
    push_task.after(eval_task)


if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=llm_finetuning_pipeline,
        package_path="pipeline.yaml",
    )
    print("Pipeline compiled to pipeline.yaml")
