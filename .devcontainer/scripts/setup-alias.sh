#!/usr/bin/env bash

set -euo pipefail

alias_definition="alias will-it-scale='uv run will-it-scale'"

for shell_config in "$HOME/.bashrc" "$HOME/.zshrc"; do
    touch "$shell_config"
    if ! grep -Fxq "$alias_definition" "$shell_config"; then
        printf '\n%s\n' "$alias_definition" >> "$shell_config"
    fi
done