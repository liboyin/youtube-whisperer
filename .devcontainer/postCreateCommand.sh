#! /bin/bash
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as root, but current user is vscode
sudo pip install -e .[dev]
