#! /bin/bash
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as user, but current user is vscode
sudo pip --disable-pip-version-check --no-cache-dir install --editable .[dev]
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.dev.txt
