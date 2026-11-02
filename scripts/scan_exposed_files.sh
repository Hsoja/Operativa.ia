#!/usr/bin/env bash
# Falla si Git rastrea archivos de configuración sensibles o si faltan reglas en .gitignore.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
status=0

# El bloque "if" evita que el patrón se tome como opción de grep
tracked=$(git ls-files | grep -E '(^|/)(\.env(\..*)?|credentials\.json|token\.json|client_secret[^/]*\.json|id_rsa)$|(^|/)secrets/|\.(db|sqlite3?|pem|key|bak|dump)$' | grep -v -E '(^|/)\.env\.example$')
if [ -n "$tracked" ]; then
  echo "FALLO: archivos sensibles rastreados por Git:"
  echo "$tracked"
  status=1
fi

for path in .env secrets/x backend/credentials.json backend/token.json backend/data/x.db backend/logs/x.jsonl backup.bak; do
  if ! git check-ignore -q "$path"; then
    echo "FALLO: .gitignore no cubre $path"
    status=1
  fi
done

[ "$status" -eq 0 ] && echo "OK: no hay archivos sensibles expuestos."
exit "$status"
