#! /bin/bash
pip3 freeze > requirements.txt
pip3 --disable-pip-version-check --no-cache-dir install -e .[dev]
pip3 freeze | grep -v youtube_whisperer > requirements.dev.txt
