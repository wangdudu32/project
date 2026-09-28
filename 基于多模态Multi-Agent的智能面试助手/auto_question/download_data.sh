#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
modelscope download --dataset swift/ChartQA --local_dir data/sft
