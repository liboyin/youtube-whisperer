#!/bin/bash

remove_dir() {
    for pattern in "$@"; do
        find . -type d -name "$pattern" -print0 | while IFS= read -r -d '' dir; do
            echo "Removing directory: $dir"
            rm -rf "$dir"
        done
    done
}

remove_file() {
    for pattern in "$@"; do
        find . -type f -name "$pattern" -print0 | while IFS= read -r -d '' file; do
            echo "Removing file: $file"
            rm "$file"
        done
    done
}

# Remove Python cache files and directories
remove_dir "__pycache__" ".mypy_cache" ".pytest_cache"

# Remove Python compiled files
remove_file "*.pyc" "*.pyd" "*.pyo"

# Remove coverage files
remove_file ".coverage"
remove_dir "htmlcov"

# Remove build and distribution directories
remove_dir "build" "dist" "*.egg-info"
