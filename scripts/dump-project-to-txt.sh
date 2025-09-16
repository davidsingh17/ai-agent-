set -euo pipefail

OUTBASE="snapshots/textdump-$(date +%F-%H%M)"
mkdir -p "$OUTBASE"
EXCL_DIRS_PRUNE='\(.git\|node_modules\|.venv\|__pycache__\|snapshots\|appsmith_stacks\|minio_data\|db_data\)'

EXCL_EXT='(png|jpg|jpeg|gif|webp|svg|ico|pdf|zip|tgz|gz|tar|xz|7z|pptx|xlsx|xls|docx|db|sqlite|woff|woff2|ttf|eot|mp3|mp4|mov|heic)'

dumper() {
  local outfile="$1"; shift
  : > "$outfile"
  {
    echo "# Dump generated $(date -u +"%F %T UTC")"
    echo "# Project root: $(pwd)"
    echo
  } >> "$outfile"

  [ "$#" -gt 0 ] || return 0
  find "$@" \
    \( -regex ".*$EXCL_DIRS_PRUNE.*" -type d \) -prune -false -o \
    -type f -print0 \
  | tr -d '\n' | xargs -0 -I '{}' sh -c '
      for f in "$@"; do
        case "$f" in
          *.*)
            ;;
        esac
        # salta binari per estensione
        if printf "%s" "$f" | grep -Eiq "\.('"$EXCL_EXT"')$"; then
          continue
        fi
        mt=$(file -b --mime-type "$f" 2>/dev/null || true)
        if printf "%s" "$mt" | grep -q "^text/"; then
          echo "===== BEGIN: $f =====" >> "'"$outfile"'"
          cat "$f" >> "'"$outfile"'"
          echo >> "'"$outfile"'"
          echo "===== END: $f =====" >> "'"$outfile"'"
          echo >> "'"$outfile"'"
        else
          case "$f" in
            *.py|*.ts|*.tsx|*.js|*.jsx|*.json|*.yml|*.yaml|*.md|*.sql|*.ini|*.toml|*.sh|*.bash|*.zsh|Dockerfile|dockerfile|*.env|*.txt|*.css|*.html|*.vue)
              echo "===== BEGIN: $f =====" >> "'"$outfile"'"
              cat "$f" >> "'"$outfile"'"
              echo >> "'"$outfile"'"
              echo "===== END: $f =====" >> "'"$outfile"'"
              echo >> "'"$outfile"'"
              ;;
          esac
        fi
      done
    ' sh {}
}
BACKEND_DIRS=()
[ -d apps/backend ] && BACKEND_DIRS+=(apps/backend)
[ -d backend ]      && BACKEND_DIRS+=(backend)

FRONTEND_DIRS=()
[ -d apps/frontend ] && FRONTEND_DIRS+=(apps/frontend)
[ -d frontend ]      && FRONTEND_DIRS+=(frontend)

CORE_CANDIDATES=(docker-compose.yml .env .env.example README.md Makefile infra)
CORE_EXIST=()
for p in "${CORE_CANDIDATES[@]}"; do [ -e "$p" ] && CORE_EXIST+=("$p"); done

OLDIFS=$IFS; IFS=$'\n'
for f in $(find . -maxdepth 1 -type f \( -name "*.md" -o -name "*.yml" -o -name "*.yaml" -o -name "*.toml" -o -name "*.ini" -o -name "Dockerfile" -o -name "*.env" -o -name "*.txt" \) | sort); do
  CORE_EXIST+=("$f")
done
IFS=$OLDIFS

[ "${#BACKEND_DIRS[@]}"  -gt 0 ] && dumper "$OUTBASE/backend.txt"  "${BACKEND_DIRS[@]}"
[ "${#FRONTEND_DIRS[@]}" -gt 0 ] && dumper "$OUTBASE/frontend.txt" "${FRONTEND_DIRS[@]}"
[ "${#CORE_EXIST[@]}"    -gt 0 ] && dumper "$OUTBASE/core.txt"     "${CORE_EXIST[@]}"

FILES_TO_COMBINE=()
[ -f "$OUTBASE/core.txt" ]     && FILES_TO_COMBINE+=("$OUTBASE/core.txt")
[ -f "$OUTBASE/backend.txt" ]  && FILES_TO_COMBINE+=("$OUTBASE/backend.txt")
[ -f "$OUTBASE/frontend.txt" ] && FILES_TO_COMBINE+=("$OUTBASE/frontend.txt")
[ "${#FILES_TO_COMBINE[@]}" -gt 0 ] && cat "${FILES_TO_COMBINE[@]}" > "$OUTBASE/ALL.txt"

{
  echo "# File tree (excluded: $EXCL_DIRS_PRUNE )"
  if command -v tree >/dev/null 2>&1; then
    tree -a -I '.git|node_modules|.venv|__pycache__|snapshots|appsmith_stacks|minio_data|db_data' -L 6
  else
    find . \( -regex ".*$EXCL_DIRS_PRUNE.*" -type d \) -prune -false -o -print | sed 's|^\./||'
  fi
} > "$OUTBASE/file_tree.txt"

echo "Done. Files in: $OUTBASE"
ls -lh "$OUTBASE"
