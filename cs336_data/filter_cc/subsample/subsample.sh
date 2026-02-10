#!/bin/bash
# High-performance Wikipedia URL subsampling for fastText training.
# Default: whitelist-only mode with 100 URLs per domain.
set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

INPUT_FILE="${1:-data/wiki/enwiki-20240420-extracted_urls.txt.gz}"
OUTPUT_FILE="${2:-data/wiki/positive_urls.txt}"
TARGET_COUNT="${3:-500000}"
PER_DOMAIN_LIMIT="${4:-5000}"
SEED="${5:-42}"
WHITELIST_ONLY="${6:-true}"  # Default: only keep whitelisted domains

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHITELIST_REGEX="${SCRIPT_DIR}/whitelist_domain.regex"
BLACKLIST_DOMAINS="${SCRIPT_DIR}/blacklist_domain.txt"
BLACKLIST_PATHS="${SCRIPT_DIR}/blacklist_path.regex"

# =============================================================================
# Utility Functions
# =============================================================================

log() { echo "[$(date '+%H:%M:%S')] $*"; }

check_dependency() {
    local cmd="$1"
    command -v "${cmd}" >/dev/null 2>&1 || {
        log "Error: '${cmd}' not found. Please install it."
        exit 1
    }
}

check_file() {
    local file="$1"
    [[ -f "${file}" ]] || {
        log "Error: File not found: ${file}"
        exit 1
    }
}

# =============================================================================
# Rule Compilation
# =============================================================================

compile_domain_blacklist() {
    # Convert plain domains to regex: example.com -> (^|\.|/)example\.com($|[/?])
    local src="$1" dst="$2"
    grep -v '^[[:space:]]*#' "${src}" | grep -v '^[[:space:]]*$' | \
        sed 's/\./\\./g; s@^@(^\\|[./])@; s@$@($\\|[/?])@' > "${dst}"
}

compile_domain_whitelist() {
    # Whitelist patterns are already regex, just filter comments
    local src="$1" dst="$2"
    grep -v '^[[:space:]]*#' "${src}" | grep -v '^[[:space:]]*$' > "${dst}"
}

# =============================================================================
# Pipeline Stages
# =============================================================================

stage_decompress() {
    # Parallel gzip decompression
    pigz -dc -p 16 "$1"
}

stage_normalize() {
    # Normalize URLs: lowercase, strip fragment/trailing slash, validate protocol
    awk '{
        if ($0 !~ /^https?:\/\// || $0 ~ /localhost|127\.0\.0\.1/) next
        url = tolower($0)
        
        # Rewrite ArXiv PDF to HTML: arxiv.org/pdf/1234.5678 -> arxiv.org/html/1234.5678
        if (url ~ /arxiv\.org\/pdf\//) {
            sub(/\/pdf\//, "/html/", url)
            sub(/\.pdf$/, "", url)
        }
        
        sub(/#.*/, "", url)
        sub(/\/$/, "", url)
        if (length(url) > 10) print url
    }'
}

stage_filter_paths() {
    # Remove URLs matching blacklisted path patterns
    local pattern_file="$1"
    rg -v -f "${pattern_file}" || cat
}

stage_filter_domains_blacklist() {
    # Remove URLs from blacklisted domains
    local pattern_file="$1"
    rg -v -f "${pattern_file}" || cat
}

stage_filter_domains_whitelist() {
    # Keep only URLs from whitelisted domains
    local pattern_file="$1"
    rg -f "${pattern_file}" || true
}

stage_deduplicate() {
    # Sort and deduplicate using all cores
    LC_ALL=C sort -u -S 50% --parallel="$(nproc)"
}

stage_shuffle() {
    # Reproducible shuffle with fixed seed
    local seed="$1"
    shuf --random-source=<(openssl enc -aes-256-ctr -pass pass:"${seed}" -nosalt </dev/zero 2>/dev/null)
}

stage_limit_per_domain() {
    # Limit URLs per domain to ensure diversity
    local limit="$1"
    awk -v limit="${limit}" '{
        match($0, /^https?:\/\/([^\/]+)/, m)
        domain = m[1]
        gsub(/^www\./, "", domain)
        if (count[domain]++ < limit) print
    }'
}

stage_truncate() {
    # Take first N lines
    head -n "$1"
}

# =============================================================================
# Main Pipeline
# =============================================================================

run_pipeline() {
    local input="$1" output="$2" target="$3" limit="$4" seed="$5" whitelist_only="$6"
    local temp_bl_domain temp_wl_domain

    # Create temp directory with cleanup trap
    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '${temp_dir}'" EXIT

    temp_bl_domain="${temp_dir}/bl_domain.regex"
    temp_wl_domain="${temp_dir}/wl_domain.regex"
    temp_bl_path="${temp_dir}/bl_path.regex"

    # Compile rules
    log "Compiling filter rules..."
    compile_domain_blacklist "${BLACKLIST_DOMAINS}" "${temp_bl_domain}"
    compile_domain_whitelist "${WHITELIST_REGEX}" "${temp_wl_domain}"
    # Reuse whitelist compiler for path regex (strips comments/empty lines)
    compile_domain_whitelist "${BLACKLIST_PATHS}" "${temp_bl_path}"

    # Build pipeline based on mode
    log "Running pipeline (whitelist_only=${whitelist_only})..."

    if [[ "${whitelist_only}" == "true" ]]; then
        # Whitelist-only mode: stricter filtering
        stage_decompress "${input}" | \
            stage_normalize | \
            stage_filter_paths "${temp_bl_path}" | \
            stage_filter_domains_blacklist "${temp_bl_domain}" | \
            stage_filter_domains_whitelist "${temp_wl_domain}" | \
            stage_deduplicate | \
            stage_shuffle "${seed}" | \
            stage_limit_per_domain "${limit}" | \
            stage_truncate "${target}" > "${output}"
    else
        # Permissive mode: only apply blacklists
        stage_decompress "${input}" | \
            stage_normalize | \
            stage_filter_paths "${temp_bl_path}" | \
            stage_filter_domains_blacklist "${temp_bl_domain}" | \
            stage_deduplicate | \
            stage_shuffle "${seed}" | \
            stage_limit_per_domain "${limit}" | \
            stage_truncate "${target}" > "${output}"
    fi
}

# =============================================================================
# Entry Point
# =============================================================================

main() {
    log "=== Wikipedia URL Subsampler ==="
    log "Input:          ${INPUT_FILE}"
    log "Output:         ${OUTPUT_FILE}"
    log "Target:         ${TARGET_COUNT}"
    log "Per-domain:     ${PER_DOMAIN_LIMIT}"
    log "Seed:           ${SEED}"
    log "Whitelist-only: ${WHITELIST_ONLY}"
    log "================================"

    # Check dependencies
    check_dependency pigz
    check_dependency rg
    check_dependency shuf
    check_dependency openssl

    # Check rule files
    check_file "${BLACKLIST_DOMAINS}"
    check_file "${BLACKLIST_PATHS}"
    check_file "${WHITELIST_REGEX}"

    # Ensure output directory exists
    mkdir -p "$(dirname "${OUTPUT_FILE}")"

    # Run pipeline
    run_pipeline "${INPUT_FILE}" "${OUTPUT_FILE}" "${TARGET_COUNT}" \
                 "${PER_DOMAIN_LIMIT}" "${SEED}" "${WHITELIST_ONLY}"

    # Report results
    local final_count
    final_count=$(wc -l < "${OUTPUT_FILE}")
    log "================================"
    log "Done! Output: ${OUTPUT_FILE}"
    log "Total URLs:  ${final_count}"
}

main "$@"