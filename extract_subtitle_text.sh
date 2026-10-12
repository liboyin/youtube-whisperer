#!/bin/bash

# Check if a file name is provided as an argument
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <srt_file>"
    exit 1
fi

# Print every line of cue text and drop only SRT structure, accepting LF or CRLF input.
# - One trailing carriage return is stripped from every line, and a UTF-8 BOM from the first.
# - Timing lines (H+:MM:SS,mmm --> H+:MM:SS,mmm, with ',' or '.' before the milliseconds and
#   optional trailing cue settings) are dropped.
# - A digits-only line is a cue index only when the next line is a timing line, so it is held
#   until that line arrives (or EOF) and otherwise printed as dialogue such as "2026".
# - Lines that are empty after stripping are blank separators and are dropped.
# The file is redirected rather than passed as an operand, so awk never treats a name
# containing '=' as a variable assignment.
awk '
function is_timing(line) {
    return line ~ /^[0-9]+:[0-9][0-9]:[0-9][0-9][,.][0-9][0-9][0-9][ \t]+-->[ \t]+[0-9]+:[0-9][0-9]:[0-9][0-9][,.][0-9][0-9][0-9]([ \t].*)?$/
}
NR == 1 { sub(/^\357\273\277/, "") }
{ sub(/\r$/, "") }
held != "" {
    if (is_timing($0)) { held = ""; next }
    print held
    held = ""
}
is_timing($0) || $0 == "" { next }
/^[0-9]+$/ { held = $0; next }
{ print }
END { if (held != "") print held }
' < "$1"

# To run this script over all .srt files:
# find . -name "*.srt" -exec sh -c './extract_subtitle_text.sh "$1" > "${1%.srt}.txt"' _ {} \;
