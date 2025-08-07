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

# Check if we're on a supported Linux distribution
if ! command -v python3 >/dev/null 2>&1; then
    print_error "Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

print_status "Detected Linux distribution..."

# Auto-detect package manager and install dependencies
if command -v pacman >/dev/null 2>&1; then
    print_status "Detected Arch Linux - using pacman"
    print_status "Installing system dependencies..."

    # Install system packages including Python dependencies
    sudo pacman -S --needed \
        python \
        python-gobject \
        python-pillow \
        python-requests \
        python-numpy \
        python-dbus \
        python-mutagen \
        gtk3 \
        cava \
        ffmpeg

    print_success "System packages installed successfully!"

elif command -v apt >/dev/null 2>&1; then
    print_status "Detected Debian/Ubuntu - using apt"
    print_status "Installing system dependencies..."

    sudo apt update
    sudo apt install -y \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gtk-3.0 \
        python3-pil \
        python3-requests \
        python3-numpy \
        python3-dbus \
        python3-mutagen \
        cava \
        ffmpeg \
        python3-pip

elif command -v dnf >/dev/null 2>&1; then
    print_status "Detected Fedora - using dnf"
    print_status "Installing system dependencies..."

    sudo dnf install -y \
        python3 \
        python3-gobject \
        python3-pillow \
        python3-requests \
        python3-numpy \
        python3-dbus \
        python3-mutagen \
        gtk3 \
        cava \
        ffmpeg \
        python3-pip

elif command -v zypper >/dev/null 2>&1; then
    print_status "Detected openSUSE - using zypper"
    print_status "Installing system dependencies..."

    sudo zypper install -y \
        python3 \
        python3-gobject \
        python3-Pillow \
        python3-requests \
        python3-numpy \
        python3-dbus-python \
        python3-mutagen \
        gtk3 \
        cava \
        ffmpeg \
        python3-pip

else
    print_warning "Could not detect package manager."
    print_warning "Please install the following packages manually:"
    echo "  - Python 3 with GTK bindings (python3-gi, python3-gi-cairo, gir1.2-gtk-3.0)"
    echo "  - Python packages: pillow, requests, numpy, dbus-python, mutagen"
    echo "  - Cava audio visualizer"
    echo "  - FFmpeg"
    read -p "Press Enter to continue after installing dependencies..."
fi

# For non-Arch systems, try to install Python packages via pip if not available from system packages
if ! command -v pacman >/dev/null 2>&1; then
    print_status "Checking for missing Python dependencies..."

    # Create a virtual environment as fallback
    if ! python3 -c "import PIL, requests, numpy, dbus, mutagen" >/dev/null 2>&1; then
        print_status "Some Python dependencies missing, creating virtual environment..."

        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi

        source venv/bin/activate
        pip install pillow requests numpy dbus-python mutagen

        print_success "Virtual environment created and dependencies installed!"
        print_warning "You'll need to activate the virtual environment before running:"
        print_warning "  source venv/bin/activate"
        print_warning "  ./ecliptic.py"
    fi
fi

print_status "Making ecliptic.py executable..."
chmod +x ecliptic.py

print_status "Testing installation..."

# Test dependencies
python3 -c "
import sys
success = True

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
    print('✓ GTK bindings working')
except Exception as e:
    print('✗ GTK bindings failed:', e)
    success = False

try:
    import PIL, requests, numpy, dbus, mutagen
    print('✓ Python dependencies working')
except Exception as e:
    print('✗ Python dependencies failed:', e)
    success = False

if not success:
    sys.exit(1)
" || {
    print_error "Dependency test failed"

    if command -v pacman >/dev/null 2>&1; then
        print_status "Trying to install missing Arch packages..."
        sudo pacman -S --needed python-pillow python-requests python-numpy python-dbus python-mutagen

        # Test again
        python3 -c "
import sys
try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
    import PIL, requests, numpy, dbus, mutagen
    print('✓ All dependencies working after package installation')
except Exception as e:
    print('✗ Dependencies still failing:', e)
    sys.exit(1)
        " || {
            print_error "Still failing after package installation. You may need to create a virtual environment."
            exit 1
        }
    else
        exit 1
    fi
}

if command -v cava >/dev/null 2>&1; then
    print_success "Cava found"
else
    print_warning "Cava not found - visualizer will be disabled"
fi

if command -v ffplay >/dev/null 2>&1; then
    print_success "FFmpeg found"
else
    print_warning "FFmpeg not found - local file playback may not work"
fi

print_success "Setup completed successfully!"
echo ""
echo "You can now run Ecliptic Music Player:"

if [ -d "venv" ]; then
    echo "  source venv/bin/activate  # (if using virtual environment)"
fi

echo "  ./ecliptic.py"
echo ""
echo "For Arch Linux users:"
echo "  All dependencies should now be installed via pacman"
echo "  No virtual environment needed"
echo ""
echo "Available command-line options:"
echo "  ./ecliptic.py --no-visualizer    # Disable audio visualizer"
echo ""
echo "Enjoy your music with Ecliptic!"
