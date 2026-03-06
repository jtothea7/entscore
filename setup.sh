#!/bin/bash
echo "==============================================="
echo "  EntScore Installation"
echo "==============================================="
echo ""

# Create virtual environment
echo "-> Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "-> Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "-> Installing Python packages..."
pip install -r requirements.txt

# Download spaCy model
echo "-> Downloading spaCy model..."
python -m spacy download en_core_web_sm

# Create necessary directories
echo "-> Creating directories..."
mkdir -p exports data logs

echo ""
echo "==============================================="
echo "  Installation Complete!"
echo "==============================================="
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env"
echo "  2. Add your DataForSEO credentials to .env"
echo "  3. Run: source venv/bin/activate"
echo "  4. Run: streamlit run app.py"
echo ""
