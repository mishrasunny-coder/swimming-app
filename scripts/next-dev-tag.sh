#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <artifact-registry-image-path>" >&2
  echo "Example: $0 us-central1-docker.pkg.dev/my-project/swimming-app/swimming-app" >&2
  exit 1
fi

image_path="$1"

# Best-effort listing; if the image has no tags yet, gcloud exits non-zero.
if ! tag_lines="$(gcloud artifacts docker tags list "$image_path" --format='value(tag)' 2>/dev/null)"; then
  tag_lines=""
fi

max_version=0
while IFS= read -r tag; do
  [[ -z "$tag" ]] && continue
  if [[ "$tag" =~ ^dev-v([0-9]+)$ ]]; then
    version="${BASH_REMATCH[1]}"
    if (( version > max_version )); then
      max_version="$version"
    fi
  fi
done <<< "$tag_lines"

next_version=$((max_version + 1))
echo "dev-v${next_version}"
