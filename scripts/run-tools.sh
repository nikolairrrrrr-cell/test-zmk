#!/usr/bin/env bash
set -euo pipefail

# Examples:
# ./scripts/run-tools.sh ves
# ./scripts/run-tools.sh pdf-zmk new

cmd="${1:-}"

if [[ -z "$cmd" ]]; then
  echo "Usage: $0 <ves|pdf-zmk|pdf-zmk2> [input]"
  exit 2
fi

case "$cmd" in
  ves)
    python -m app.cli ves run \
      --positions "ves/test_positions.txt" \
      --online \
      --force-refresh
    ;;
  pdf-zmk)
    input="${2:-}"
    if [[ -z "$input" ]]; then
      echo "Usage: $0 pdf-zmk <input_dir>"
      exit 2
    fi
    python -m app.cli pdf-zmk full --input-dir "$input"
    ;;
  pdf-zmk2)
    input="${2:-}"
    if [[ -z "$input" ]]; then
      python -m app.cli pdf-zmk2 full
    elif [[ -d "$input" ]]; then
      python -m app.cli pdf-zmk2 full --input-dir "$input"
    else
      python -m app.cli pdf-zmk2 run --input "$input"
    fi
    ;;
  *)
    echo "Unknown command: $cmd"
    exit 2
    ;;
esac

