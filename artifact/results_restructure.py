#!/usr/bin/env python3
import os
import shutil
import json

def restructure():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    
    # Define source and destination paths
    src_3x_runs = os.path.join(base_dir, "artifact", "results_3x_runs")
    src_32k_baseline = os.path.join(base_dir, "artifact", "results_32k_baseline")
    
    dest_gemma = os.path.join(base_dir, "results", "gemma4_26b_bf16")
    dest_nemotron = os.path.join(base_dir, "results", "nemotron3_super_nvfp4")
    
    # Create destinations
    os.makedirs(dest_gemma, exist_ok=True)
    os.makedirs(dest_nemotron, exist_ok=True)
    
    print(f"Created results folder structure:")
    print(f"  - {dest_gemma}")
    print(f"  - {dest_nemotron}")
    
    # 1. Migrate Gemma-4-26B runs
    if os.path.exists(src_3x_runs):
        print(f"Migrating Gemma-4 3x runs from {src_3x_runs}...")
        for item in os.listdir(src_3x_runs):
            src_path = os.path.join(src_3x_runs, item)
            dest_path = os.path.join(dest_gemma, item)
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
        print("Gemma-4 runs migrated successfully.")
    else:
        print(f"Warning: Gemma-4 source folder {src_3x_runs} not found.")

    # 2. Write metadata.json for Gemma-4
    metadata_gemma = {
        "experiment_id": "gemma4_26b_bf16",
        "display_name": "Gemma-4-26B-MoE (BF16)",
        "model_id": "gemma-4-26b-moe",
        "model_path": "/home/dgx-spark-01/ai_data/models/gemma-4-26b-moe",
        "precision": "BF16",
        "architecture": "Mixture-of-Experts",
        "parameter_count": "26B (3.5B active)",
        "context_window_native": 32768,
        "context_window_used": 32768,
        "vllm_endpoint": "http://localhost:8000/v1",
        "tensor_parallel_size": 2,
        "hardware": "2x DGX Spark (NVIDIA GB10, 128GB each)",
        "runs": 3,
        "total_scenarios": 81,
        "overall_f1": 0.9248,
        "notes": "Completed 3 runs. Shows 92.48% overall F1 with IP budget boost."
    }
    
    with open(os.path.join(dest_gemma, "metadata.json"), "w") as f:
        json.dump(metadata_gemma, f, indent=2)
    print("Created metadata.json for Gemma-4.")

    # 3. Write metadata.json for Nemotron-3-Super
    metadata_nemotron = {
        "experiment_id": "nemotron3_super_nvfp4",
        "display_name": "Nemotron-3-Super-120B (NVFP4)",
        "model_id": "Nemotron-3-Super-NVFP4",
        "model_path": "/home/dgx-spark-01/ai_data/models/Nemotron-3-Super-NVFP4",
        "precision": "NVFP4 (Weights: 4-bit, KV Cache: FP8)",
        "architecture": "Mamba-Transformer MoE",
        "parameter_count": "120B (12B active)",
        "context_window_native": 262144,
        "context_window_used": 32768,
        "vllm_endpoint": "http://localhost:8000/v1",
        "tensor_parallel_size": 2,
        "hardware": "2x DGX Spark (NVIDIA GB10, 128GB each)",
        "notes": "Evaluated using NVFP4 weights and FP8 KV cache."
    }
    
    with open(os.path.join(dest_nemotron, "metadata.json"), "w") as f:
        json.dump(metadata_nemotron, f, indent=2)
    print("Created metadata.json template for Nemotron.")

if __name__ == "__main__":
    restructure()
