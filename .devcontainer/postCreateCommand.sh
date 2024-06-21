#! /bin/bash
pip3 freeze | grep -v whisperer > requirements.txt
# deployment dependencies are installed as user, but current user is vscode
sudo pip3 --disable-pip-version-check --no-cache-dir install --editable .[dev]
pip3 freeze | grep -v whisperer > requirements.dev.txt
