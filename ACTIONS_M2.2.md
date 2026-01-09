# ACTIONS_M2.2.md — EUR-Lex download + manifest (CELEX 02023R1803-20250730)

.env (sessione): `~/Tesi/IIAA/.env`  
Verifica (esempi): `pwd` deve essere `~/Tesi/IIAA` e la venv attiva (`source .venv/bin/activate`).

## Comandi eseguiti

```bash
cd ~/Tesi/IIAA
source .venv/bin/activate

# (Fix) Riscrittura completa del downloader per eliminare corruzione da copy/paste
cp apps/eu_download.py apps/eu_download.py.BAD_$(date -u +%Y%m%d_%H%M%SZ).py
cat > apps/eu_download.py <<'EOF'
# (contenuto del file come fornito in chat)
EOF

# Check sintattico
python -m py_compile apps/eu_download.py
echo "OK: syntax"

# Download EUR-Lex (HTML + PDF, EN + IT) per CELEX consolidato
python apps/eu_download.py \
  --celex 02023R1803-20250730 \
  --doc-id eu_oj_02023R1803_20250730 \
  --langs EN,IT \
  --formats html,pdf

# Verifiche artefatti e manifest
ls -lah corpus/legal/eu_oj/original | tail -n 10
ls -lah corpus/legal/eu_oj/oracle_html | tail -n 10
tail -n 6 corpus/legal/eu_oj/manifests/manifest_eurlex_downloads.jsonl
ls -lah telemetry/eu_download | tail -n 10
```

## Output atteso / osservato

- PDF scaricati:
  - `corpus/legal/eu_oj/original/eu_oj_02023R1803_20250730_EN.pdf`
  - `corpus/legal/eu_oj/original/eu_oj_02023R1803_20250730_IT.pdf`
- HTML scaricati:
  - `corpus/legal/eu_oj/oracle_html/eu_oj_02023R1803_20250730_EN.html`
  - `corpus/legal/eu_oj/oracle_html/eu_oj_02023R1803_20250730_IT.html`
- Manifest append-only:
  - `corpus/legal/eu_oj/manifests/manifest_eurlex_downloads.jsonl`
  - Campi: `accessed_at_utc`, `http_status`, `bytes`, `sha256`, `license_notice_url`, `redistribution_allowed`.

## Nota

- La cartella `telemetry/eu_download/` risultava vuota perché `src.telemetry` non veniva importato (fallback silenzioso).  
  Nel passo successivo si aggiunge un `sys.path` fix (project root) per abilitare telemetria anche dagli script in `apps/`.
