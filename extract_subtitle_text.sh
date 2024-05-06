#!/bin/bash

# Check if a file name is provided as an argument
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <srt_file>"
    exit 1
fi

# Use sed to process the SRT file
# -e '/-->/d' will delete the time range lines
# -e '/^[0-9]*$/d' will delete lines that only contain numbers (sequence numbers)
# -e '/^$/d' will delete empty lines
sed -e '/-->/d' -e '/^[0-9]*$/d' -e '/^$/d' "$1"
