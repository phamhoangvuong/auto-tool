#!/usr/bin/env bash
set -e

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements..."
pip install -r requirements.txt

echo "No need to install Chrome via apt - using webdriver-manager to handle chromedriver"

echo "Build complete! Server will use headless Chrome via Selenium + webdriver-manager"
