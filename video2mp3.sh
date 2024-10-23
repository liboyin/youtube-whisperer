#!/bin/bash

# Use the provided argument for the directory, or fallback to the default directory
MONITOR_DIR_PATH="${1:-assets}"

while true; do
    file_found=false
    while IFS= read -r -d '' input_file_path; do
        output_file_path="${input_file_path%.*}.mp3"
        if [[ ! -f "$output_file_path" ]]; then
            file_found=true
            echo "New file detected: $input_file_path"
            ffmpeg -i "$input_file_path" -vn -acodec libmp3lame -q:a 2 "$output_file_path"
            if [[ $? -eq 0 ]]; then
                echo "Audio extraction successful: $output_file_path"
            else
                echo "Audio extraction failed for: $input_file_path"
            fi
        fi
    done < <(find "$MONITOR_DIR_PATH" \( -name "*.mkv" -o -name "*.mp4" \) -print0)
    if [ "$file_found" = false ]; then
        echo "No new file detected. Sleeping for 60 seconds..."
        sleep 60
    fi
done
