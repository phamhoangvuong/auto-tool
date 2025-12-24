#!/usr/bin/env bash
set -e

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Cài Google Chrome headless (cách mới, không dùng apt-key deprecated)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list

apt-get update -qq
apt-get install -y google-chrome-stable

# Cài thêm fonts và lib cần cho Selenium
apt-get install -y fonts-liberation libnss3 libgdk-pixbuf2.0-0 libgtk-3-0 libxss1 libasound2 xvfb

echo "Chrome installed successfully!"
google-chrome --version
