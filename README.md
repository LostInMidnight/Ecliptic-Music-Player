# Ecliptic Music Player

A modern Linux music player with real-time audio visualization using Cava.
<p align="center">
  <img src="Icons/example1.gif" width="45%" />
  <img src="Icons/example2.gif" width="45%" />
</p>

## Features

- Real-time audio visualization with Cava
- MPRIS2 support for popular media players (Spotify, VLC, Firefox, etc.)
- Local music file playback

## Quick Start

### Install Dependencies(Automated)
```bash
git clone <repository-url>
cd ecliptic-music-player
chmod +x setup.sh
./setup.sh
```

### Manual Installation

#### Dependencies

Install required system packages:

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 cava python3-pip ffmpeg
```

**Arch Linux:**
```bash
sudo pacman -S python-gobject gtk3 cava python-pip ffmpeg
```

**Fedora:**
```bash
sudo dnf install python3-gobject gtk3 cava python3-pip ffmpeg
```

Install Python dependencies:
```bash
pip3 install --user -r requirements.txt
```

### Running the Application()


```bash
# Using install script
chmod +x install.sh
sudo ./install.sh

# Or using Makefile
sudo make install

# Then run from anywhere
ecliptic
```

## Usage

### MPRIS2 Players
The app automatically detects and controls MPRIS2-compatible players:
- Spotify
- VLC
- Firefox/Chrome (Buggy, Not Recommended)

### Local Music Files
- Click the folder icon to load a music directory
- Click the playlist icon to manage playback options
- Supports MP3, FLAC, OGG, M4A, WAV formats

### Audio Visualization
- Requires Cava to be installed
- Automatically starts when music plays

## Command Line Options

```bash
./ecliptic.py --help                 # Show help
./ecliptic.py                        # Full player mode (default)
./ecliptic.py --no-visualizer        # Disable audio visualizer
```


## Development

### Building from Source
```bash
git clone <repository-url>
cd ecliptic-music-player
make deps          # Install dependencies
make test          # Run tests
python3 ecliptic.py # Run application
```


## Troubleshooting

### Cava Not Working
- Ensure cava is installed: `which cava`
- Check audio permissions
- Try running cava manually: `cava`

### No Media Players Detected
- Install an MPRIS2-compatible player
- Start the media player before launching Ecliptic
- Check D-Bus service: `busctl --user list | grep mpris`

### Album Art Not Loading
- Check internet connection for online sources
- Verify local image file permissions
- Some players may not provide album art

### Audio Issues
- Install ffmpeg for local file playback
- Check audio output device settings
- Verify file format support

### Installation Issues
- Run `make test` to check dependencies
- Ensure all system packages are installed
- Check Python version (3.6+ required)

### Permission Issues
- For user installation: `./install.sh` (without sudo)
- For system installation: `sudo ./install.sh`
- Ensure `~/.local/bin` is in your PATH for user installations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly (`make test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with GTK3 and Python
- Audio visualization powered by Cava
- MPRIS2 integration for media player control
- Album art color extraction using PIL
- Inspired By PlasMusic Audio Player

---

**Ecliptic Music Player**
