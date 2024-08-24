#!/bin/bash

LOCAL_DIR="$HOME/.whisper"
REMOTE_DIR="$LOCAL_DIR/Transcode"

if [ $# -ne 1 ]; then
    echo "Usage: $0 (in|out)"
    exit 1
fi

case $1 in
    "in")
        files_to_copy=("$REMOTE_DIR"/2024*.mp4)
        if ls -hal "${files_to_copy[@]}"; then
            cp "${files_to_copy[@]}" "$LOCAL_DIR"
            echo "Number of MP4 files copied: ${#files_to_copy[@]}"
        fi
        ;;
    "out")
        files_to_move=("$LOCAL_DIR"/2024*.srt)
        files_to_delete=("$LOCAL_DIR"/2024*.mp4 "$LOCAL_DIR"/2024*.seg)
        files_count=0

        if ls -hal "${files_to_move[@]}"; then
            mv "${files_to_move[@]}" "$REMOTE_DIR"
            files_count=${#files_to_move[@]}
        fi

        echo "Number of SRT files moved: $files_count"
        files_count=0

        for ext in mp4 seg; do
            files_to_remove=("$LOCAL_DIR"/2024*."$ext")
            if ls -hal "${files_to_remove[@]}"; then
                rm "${files_to_remove[@]}"
                files_count=$((files_count + ${#files_to_remove[@]}))
            fi
        done
        
        echo "Number of MP4/SEG files deleted: $files_count"
        ;;
    *)
        echo "Error: unexpected argument $1"
        exit 1
        ;;
esac
