#!/bin/bash

# Check if a directory path is provided as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <directory_path>"
  exit 1
fi

# Get the directory path from the first argument
directory_path="$1"

# Check if the provided directory path exists
if [ ! -d "$directory_path" ]; then
  echo "Error: Directory '$directory_path' not found."
  exit 1
fi

# Loop through all .mp4 files in the provided directory
for mp4_file in "$directory_path"/*.mp4; do

  # Construct the name of the corresponding .srt file
  srt_file="${mp4_file%.mp4}.srt"

  # Check if the .srt file exists
  if [ ! -f "$srt_file" ]; then
    # If the .srt file doesn't exist, print the .mp4 filename
    echo "$mp4_file"
  fi
done
