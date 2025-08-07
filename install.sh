#!/bin/bash

set -e

echo "==================================="
echo "   Ecliptic Music Player Setup     "
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're on Arch Linux
if ! command -v pacman >/dev/null 2>&1; then
    print_error "This script is designed for Arch Linux. Use the original install.sh for other distributions."
    exit 1
fi

print_status "Detected Arch Linux - installing dependencies via pacman"

# Install system dependencies using pacman
print_status "Installing system packages..."
sudo pacman -S --needed \
    python \
    python-gobject \
    python-cairo \
    gtk3 \
    cava \
    ffmpeg \
    python-pillow \
    python-requests \
    python-numpy \
    python-dbus \
    python-mutagen \
    python-pip

print_success "System packages installed successfully"

# Check if running as root for system installation
if [[ $EUID -eq 0 ]]; then
    INSTALL_PREFIX="/usr/local"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/pixmaps"
    print_status "Installing system-wide..."
else
    INSTALL_PREFIX="$HOME/.local"
    DESKTOP_DIR="$HOME/.local/share/applications"
    ICON_DIR="$HOME/.local/share/pixmaps"
    print_status "Installing for current user..."

    # Create directories if they don't exist
    mkdir -p "$DESKTOP_DIR"
    mkdir -p "$ICON_DIR"
    mkdir -p "$INSTALL_PREFIX/bin"
fi

# Check for required commands
print_status "Verifying dependencies..."

missing_deps=()

if ! command -v python3 >/dev/null 2>&1; then
    missing_deps+=("python")
fi

if ! command -v cava >/dev/null 2>&1; then
    missing_deps+=("cava")
fi

if ! command -v ffplay >/dev/null 2>&1; then
    missing_deps+=("ffmpeg")
fi

# Check for Python modules
if ! python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null; then
    missing_deps+=("python-gobject")
fi

if ! python3 -c "import PIL" 2>/dev/null; then
    missing_deps+=("python-pillow")
fi

if ! python3 -c "import requests" 2>/dev/null; then
    missing_deps+=("python-requests")
fi

if ! python3 -c "import numpy" 2>/dev/null; then
    missing_deps+=("python-numpy")
fi

if ! python3 -c "import dbus" 2>/dev/null; then
    missing_deps+=("python-dbus")
fi

if ! python3 -c "import mutagen" 2>/dev/null; then
    missing_deps+=("python-mutagen")
fi

if [ ${#missing_deps[@]} -ne 0 ]; then
    print_error "Still missing dependencies: ${missing_deps[*]}"
    print_status "Trying to install missing packages..."
    sudo pacman -S --needed ${missing_deps[*]}
fi

print_status "Testing Python modules..."
python3 -c "
import sys
print('Python version:', sys.version)

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
    print('✓ GTK bindings working')
except Exception as e:
    print('✗ GTK bindings failed:', e)
    sys.exit(1)

try:
    import PIL, requests, numpy, dbus, mutagen
    print('✓ All Python dependencies working')
except Exception as e:
    print('✗ Python dependencies failed:', e)
    sys.exit(1)

print('✓ All tests passed!')
"

if [ $? -ne 0 ]; then
    print_error "Dependency test failed"
    exit 1
fi

print_status "Installing application files..."

# Copy main application with proper shebang
cp ecliptic.py "$INSTALL_PREFIX/bin/ecliptic"
chmod +x "$INSTALL_PREFIX/bin/ecliptic"

# Fix the shebang to ensure it works properly
sed -i '1s|^.*|#!/usr/bin/env python3|' "$INSTALL_PREFIX/bin/ecliptic"

print_success "Main application installed to $INSTALL_PREFIX/bin/ecliptic"

# Create a proper desktop entry
print_status "Creating desktop entry..."
cat > "$DESKTOP_DIR/ecliptic.desktop" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Ecliptic Music Player
Comment=Modern Linux music player with audio visualization
Exec=ecliptic
Icon=ecliptic-music-player
Terminal=false
Categories=AudioVideo;Audio;Player;
Keywords=music;player;audio;visualizer;
StartupNotify=true
MimeType=audio/mpeg;audio/mp3;audio/flac;audio/ogg;audio/mp4;audio/wav;audio/x-wav;audio/vorbis;
EOF

print_success "Desktop entry created"

# Create a default icon if none exists
if [ ! -f "ecliptic-icon.png" ]; then
    print_status "Creating default application icon..."

    # Create a simple SVG icon and convert it to PNG using available tools
    cat > /tmp/ecliptic-icon.svg << 'EOF'
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4A90E2;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#357ABD;stop-opacity:1" />
    </linearGradient>
  </defs>
  <circle cx="64" cy="64" r="60" fill="url(#bg)" stroke="#2C5AA0" stroke-width="4"/>
  <circle cx="64" cy="64" r="20" fill="none" stroke="white" stroke-width="4"/>
  <line x1="84" y1="64" x2="84" y2="34" stroke="white" stroke-width="4" stroke-linecap="round"/>
  <text x="64" y="100" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="14" font-weight="bold">♪</text>
</svg>
EOF

    # Try to convert SVG to PNG using available tools
    if command -v inkscape >/dev/null 2>&1; then
        inkscape /tmp/ecliptic-icon.svg --export-filename="$ICON_DIR/ecliptic-music-player.png" --export-width=128 --export-height=128 2>/dev/null
    elif command -v convert >/dev/null 2>&1; then
        convert /tmp/ecliptic-icon.svg -resize 128x128 "$ICON_DIR/ecliptic-music-player.png" 2>/dev/null
    elif command -v rsvg-convert >/dev/null 2>&1; then
        rsvg-convert -w 128 -h 128 /tmp/ecliptic-icon.svg -o "$ICON_DIR/ecliptic-music-player.png" 2>/dev/null
    else
        print_warning "No SVG conversion tool found. Installing a generic icon..."
        # Create a simple colored square as fallback
        python3 -c "
from PIL import Image, ImageDraw, ImageFont
import os
img = Image.new('RGBA', (128, 128), (74, 144, 226, 255))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 108, 108], outline=(255,255,255,255), width=4)
draw.ellipse([44, 44, 84, 84], outline=(255,255,255,255), width=4)
draw.line([84, 64, 84, 34], fill=(255,255,255,255), width=4)
try:
    font = ImageFont.truetype('/usr/share/fonts/TTF/arial.ttf', 24)
except:
    font = ImageFont.load_default()
draw.text((64, 90), '♪', fill=(255,255,255,255), font=font, anchor='mm')
img.save('$ICON_DIR/ecliptic-music-player.png')
print('Created fallback icon')
"
    fi

    rm -f /tmp/ecliptic-icon.svg
    print_success "Default icon created"
else
    # Copy existing icon
    cp ecliptic-icon.png "$ICON_DIR/ecliptic-music-player.png"
    print_success "Custom icon installed"
fi

# Make desktop entry executable
chmod +x "$DESKTOP_DIR/ecliptic.desktop"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    if [[ $EUID -eq 0 ]]; then
        update-desktop-database /usr/share/applications
    else
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    print_success "Desktop database updated"
fi

# Update icon cache
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    if [[ $EUID -eq 0 ]]; then
        gtk-update-icon-cache -f -t /usr/share/pixmaps 2>/dev/null || true
    else
        gtk-update-icon-cache -f -t "$HOME/.local/share/pixmaps" 2>/dev/null || true
    fi
    print_success "Icon cache updated"
fi

# Test the installation
print_status "Testing installation..."
if command -v ecliptic >/dev/null 2>&1; then
    print_success "Ecliptic command is available in PATH"
elif [ -x "$INSTALL_PREFIX/bin/ecliptic" ]; then
    print_success "Ecliptic installed successfully"
    if [[ $EUID -ne 0 ]]; then
        # Check if ~/.local/bin is in PATH
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            print_warning "~/.local/bin is not in your PATH"
            print_status "Add this line to your ~/.bashrc or ~/.zshrc:"
            print_status "export PATH=\"\$HOME/.local/bin:\$PATH\""
            print_status "Then run: source ~/.bashrc (or source ~/.zshrc)"
        fi
    fi
else
    print_error "Installation may have failed"
fi

# Check desktop entry
if [ -f "$DESKTOP_DIR/ecliptic.desktop" ]; then
    print_success "Desktop entry installed successfully"
    if desktop-file-validate "$DESKTOP_DIR/ecliptic.desktop" 2>/dev/null; then
        print_success "Desktop entry is valid"
    else
        print_warning "Desktop entry validation failed (but should still work)"
    fi
else
    print_error "Desktop entry installation failed"
fi

print_success ""
print_success "Installation completed successfully!"
print_success ""
echo "You can now run Ecliptic Music Player by:"
echo "  1. Searching for 'Ecliptic' in your application menu"
echo "  2. Running 'ecliptic' from the command line"
echo "  3. Running '$INSTALL_PREFIX/bin/ecliptic' directly"
echo ""
echo "If the app doesn't appear in your application menu:"
echo "  1. Log out and log back in"
echo "  2. Or restart your desktop environment"
echo "  3. Or run: killall -HUP gnome-shell (for GNOME)"
echo ""
echo "Features available:"
echo "  ✓ Real-time audio visualization with Cava"
echo "  ✓ Dynamic themes from album artwork"
echo "  ✓ MPRIS2 media player control (Spotify, VLC, etc.)"
echo "  ✓ Local music file playback"
echo "  ✓ Playlist management"
echo "  ✓ Beautiful blurred album art backgrounds"
echo ""
echo "Quick start:"
echo "  1. Start playing music in Spotify, VLC, or another MPRIS2 player"
echo "  2. Launch Ecliptic to see the visualizer and controls"
echo "  3. Or use the folder button to play local music files"
echo ""
print_success "Enjoy your music with Ecliptic! 🎵"
