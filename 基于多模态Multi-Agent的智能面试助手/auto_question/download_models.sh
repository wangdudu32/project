#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
modelscope download --model Qwen/Qwen2.5-VL-7B-Instruct --local_dir models/qwen2.5vl
