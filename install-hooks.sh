#!/usr/bin/env bash
# Point git at the in-repo hooks. Run once after cloning.
set -e
git config core.hooksPath .githooks
chmod +x .githooks/*
echo "git hooks installed (core.hooksPath = .githooks)"
