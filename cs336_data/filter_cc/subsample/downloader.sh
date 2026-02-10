#!/bin/bash
set -euo pipefail

# Configuration
URLS_FILE="data/wiki/subsmaple_urls.txt"
URLS_DIR="data/wiki/urls"
WARCS_DIR="data/wiki/warcs"
OUTPUT_FILE="data/wiki/subsample.warc.gz"
CHUNK_SIZE=1000
PARALLEL_JOBS=128

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check dependencies
for cmd in wget parallel split cat; do
    command -v "$cmd" &> /dev/null || error "Missing: $cmd (install with: sudo apt-get install $cmd parallel)"
done

# Check input file
[ -f "$URLS_FILE" ] || error "Input file not found: $URLS_FILE"

# Setup
log "Setting up directories..."
mkdir -p "$URLS_DIR" "$WARCS_DIR"

# Split URLs
log "Splitting $(wc -l < "$URLS_FILE") URLs into chunks of $CHUNK_SIZE..."
rm -f "$URLS_DIR"/urls_chunk_*
split -l "$CHUNK_SIZE" "$URLS_FILE" "$URLS_DIR/urls_chunk_"
log "Created $(ls -1 "$URLS_DIR"/urls_chunk_* | wc -l) chunks"

# Download
log "Starting parallel download with $PARALLEL_JOBS jobs..."
cd "$URLS_DIR" || exit 1

parallel -j"$PARALLEL_JOBS" --line-buffer --retries 3 '
    id={#}
    log="../warcs/warc_${id}.log"
    
    echo "[$(date +"%H:%M:%S")] Starting chunk ${id}" >> "$log"
    
    wget \
        --timeout=10 \
        --tries=3 \
        --retry-connrefused \
        --wait=0.5 --random-wait \
        --waitretry=10 \
        --user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36" \
        --max-redirect=5 \
        --warc-file=../warcs/warc_${id} \
        --warc-max-size=1024m \
        -i {} \
        -O /dev/null \
        -o "$log" 2>&1
    
    code=$?
    echo "[$(date +"%H:%M:%S")] Finished chunk ${id} (exit: $code)" >> "$log"
    [ $code -eq 0 ] && echo "✓ Chunk ${id}" || echo "✗ Chunk ${id} failed" >&2
' ::: urls_chunk_*

cd - > /dev/null

# Merge
log "Merging WARC files..."
cat "$WARCS_DIR"/*.warc.gz > "$OUTPUT_FILE"

# Summary
log "Done!"
echo ""
echo "=========================================="
echo "Summary:"
echo "  Input:  $URLS_FILE ($(wc -l < "$URLS_FILE") URLs)"
echo "  Chunks: $(ls -1 "$URLS_DIR"/urls_chunk_* | wc -l)"
echo "  WARCs:  $(ls -1 "$WARCS_DIR"/*.warc.gz | wc -l)"
echo "  Output: $OUTPUT_FILE ($(du -h "$OUTPUT_FILE" | cut -f1))"
echo "  Errors: $(grep -ic "error\|failed" "$WARCS_DIR"/*.log 2>/dev/null || echo 0)"
echo "=========================================="
echo ""

# Cleanup
# rm -f "$URLS_DIR"/urls_chunk_*
# rm -f "$WARCS_DIR"/*.warc.gz

log "Check logs in: $WARCS_DIR/*.log"

