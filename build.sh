#!/bin/bash

echo "Installing system dependencies..."

# Update package list
apt-get update

# Install Tesseract OCR and dependencies
apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-tha \
    libtesseract-dev \
    libleptonica-dev

# Verify installation
echo "Tesseract version:"
tesseract --version

echo "Available languages:"
tesseract --list-langs

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Build completed successfully!"
