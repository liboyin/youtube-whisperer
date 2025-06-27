#! /bin/bash
pip freeze | grep -v "youtube-whisperer\|youtube_whisperer" > requirements.txt
# deployment dependencies are installed as root, but current user is vscode
sudo pip install -e .[dev]
# install Gemini CLI
sudo apt-get update
sudo apt-get install -y --no-install-recommends nodejs npm
sudo npm install -g @google/gemini-cli
