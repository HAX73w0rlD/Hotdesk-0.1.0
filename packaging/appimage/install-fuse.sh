#!/usr/bin/env bash
set -Eeuo pipefail
if ldconfig -p 2>/dev/null | grep -Eq 'libfuse\.so\.2|libfuse3\.so\.3'; then
  echo 'FUSE ist vorhanden.'
  exit 0
fi
printf '%s\n' 'FUSE fehlt. Installation erfordert sudo und eine Paketquelle.'
read -r -p 'Fortfahren? [y/N] ' answer
[[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]] || exit 1
if command -v apt-get >/dev/null; then sudo apt-get update; sudo apt-get install -y libfuse2t64 || sudo apt-get install -y libfuse2 || sudo apt-get install -y fuse3
elif command -v dnf >/dev/null; then sudo dnf install -y fuse
elif command -v pacman >/dev/null; then sudo pacman -S --needed fuse2
else echo 'Distribution nicht unterstützt.' >&2; exit 1; fi
echo 'FUSE ist jetzt installiert.'
