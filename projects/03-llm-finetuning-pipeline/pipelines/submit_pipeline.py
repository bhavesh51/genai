"""
Project 3 – LLM Fine-tuning Pipeline
Pipeline submission script
"""
import argparse
import os
import sys
from pathlib import Path

import kfp
from kfp.client import Client

from pipelines.finetuning_pipeline import llm_finetuning_pipeline


def submit_pipeline(
    experiment_name: str,
    run_name: str,
    pipeline_params: dict,
    kfp_host: str,
    token: str,
):
    client = Client(
        host=kfp_host,
        existing_token=token,
        verify_ssl=True,
    )

    # Compile pipeline
    pipeline_path = "/tmp/finetuning_pipeline.yaml"
    kfp.compiler.Compiler().compile(llm_finetuning_pipeline, pipeline_path)

    # Create or get experiment
    try:
        experiment = client.create_experiment(experiment_name)
    except Exception:
        experiment = client.get_experiment(experiment_name=experiment_name)

    run = client.create_run_from_pipeline_package(
        pipeline_file=pipeline_path,
        arguments=pipeline_params,
        run_name=run_name,
        experiment_name=experiment_name,
        enable_caching=True,
    )
    print(f"Pipeline run submitted: {run.run_id}")
    print(f"Monitor at: {kfp_host}/#/runs/details/{run.run_id}")
    return run.run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit fine-tuning pipeline to RHOAI DSP")
    parser.add_argument("--experiment", required=True, help="Experiment name")
    parser.add_argument("--run-name", required=True, help="Run name")
    parser.add_argument(
        "--kfp-host",
        default=os.environ.get(
            "KFP_HOST",
            "https://ds-pipeline-dspa.rhoai-namespace.svc.cluster.local:8888",
        ),
    )
    parser.add_argument("--token", default=os.environ.get("OCP_TOKEN", ""))
    parser.add_argument("--base-model", default="ibm-granite/granite-3.1-8b-instruct")
    parser.add_argument("--dataset-s3-path", required=True)
    parser.add_argument("--model-version", default="1.0.0")
    args = parser.parse_args()

    params = {
        "base_model_name": args.base_model,
        "dataset_s3_path": args.dataset_s3_path,
        "model_version": args.model_version,
    }
    submit_pipeline(args.experiment, args.run_name, params, args.kfp_host, args.token)
