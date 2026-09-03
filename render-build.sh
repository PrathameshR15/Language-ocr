#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing system dependencies..."
# Update apt and install Tesseract along with required Indic language packs
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar tesseract-ocr-ben tesseract-ocr-guj tesseract-ocr-tam tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-mal tesseract-ocr-urd poppler-utils ffmpeg libsm6 libxext6 libgl1

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
