#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
import cairo
import struct
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import subprocess
import json
import time
import threading
import numpy as np
import math
import os
import urllib.request
import io
import argparse
from PIL import Image, ImageEnhance, ImageFilter
import requests
import colorsys
import hashlib
import tempfile
import select
import signal
import glob
import random
from pathlib import Path
import threading
import queue
import subprocess
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.id3 import ID3NoHeaderError
import base64

class CavaVisualizer:
    def __init__(self, callback=None):
        self.callback = callback
        self.process = None
        self.running = False
        self.bars = 100
        self.points = [0] * self.bars
        self.max_value = 255.0
        self.smoothing_factor = 0.7
        self.config_content = self.create_cava_config()

    def create_cava_config(self):
        return f"""
[general]
mode = waves
framerate = 60
autosens = 1
bars = {self.bars}
[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
channels = mono
mono_option = average
[smoothing]
noise_reduction = 20
"""
    def start(self):
        if self.running:
            return

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
                f.write(self.config_content)
                config_path = f.name

            self.process = subprocess.Popen(
                ['cava', '-p', config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )

            self.running = True

            self.read_thread = threading.Thread(target=self._read_data, daemon=True)
            self.read_thread.start()

            print("Cava audio visualizer started")

        except FileNotFoundError:
            print("Cava not found. Install with: sudo apt install cava")
        except Exception as e:
            print(f"Failed to start cava: {e}")

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except:
                pass
            self.process = None
        print("Cava audio visualizer stopped")

    def _read_data(self):
        buffer = ""

        while self.running and self.process and self.process.poll() is None:
            try:
                char = self.process.stdout.read(1).decode('utf-8')
                if not char:
                    time.sleep(0.01)
                    continue
                buffer += char

                if '\n' in buffer:
                    lines = buffer.split('\n')
                    buffer = lines[-1]

                    for line in lines[:-1]:
                        if line.strip():
                            raw_values = [float(x) for x in line.strip().split(';') if x.strip()]
                            if len(raw_values) == self.bars:
                                normalized_points = [math.sqrt(i / 700.0) for i in raw_values]

                                if hasattr(self, 'prev_points'):
                                    smoothed_points = []
                                    for i, point in enumerate(normalized_points):
                                        if i < len(self.prev_points):
                                            smooth_val = (self.prev_points[i] * self.smoothing_factor +
                                                        point * (1 - self.smoothing_factor))
                                        else:
                                            smooth_val = point
                                        smoothed_points.append(smooth_val)
                                    self.prev_points = smoothed_points
                                    self.points = smoothed_points
                                else:
                                    self.prev_points = normalized_points
                                    self.points = normalized_points

                                if self.callback:
                                    GLib.idle_add(self.callback, self.points.copy())

            except Exception as e:
                if self.running:
                    print(f"Cava read error: {e}")
                break

class VisualizerWidget(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()

        self.points = [0] * 200
        self.color = (1.0, 1.0, 1.0, 0.6)
        self.colors = [(1.0, 1.0, 1.0), (0.9, 0.9, 0.9), (0.8, 0.8, 0.8)]

        self.connect('draw', self.on_draw)

    def set_points(self, points):
        if points and len(points) > 0:
            self.points = points
            self.queue_draw()

    def set_color(self, r, g, b, a=0.8):
        self.color = (r, g, b, a)
        self.queue_draw()

    def interpolate_color(self, colors, position):
        if len(colors) == 1:
            color = colors[0]
            return color[0], color[1], color[2]

        segment = position * (len(colors) - 1)
        index = int(segment)
        fraction = segment - index

        if index >= len(colors) - 1:
            color = colors[-1]
        else:
            c1 = colors[index]
            c2 = colors[index + 1]
            color = (
                c1[0] + (c2[0] - c1[0]) * fraction,
                c1[1] + (c2[1] - c1[1]) * fraction,
                c1[2] + (c2[2] - c1[2]) * fraction
            )

        return color

    def on_draw(self, widget, cr):
        allocation = widget.get_allocation()
        width = allocation.width
        height = allocation.height

        if not self.points:
            cr.set_source_rgba(*self.color)
            cr.move_to(0, height / 2)
            for x in range(width):
                t = x / width * 2 * math.pi
                y = height / 2 + math.sin(t) * height * 0.2
                cr.line_to(x, y)
            cr.line_to(width, height)
            cr.line_to(0, height)
            cr.close_path()
            cr.fill()
            return False

        ls = len(self.points)
        if ls < 2:
            return False

        points = []

        x = 0
        y = (1.0 - self.points[0]) * height
        points.extend([x, y])

        for i in range(ls - 1):
            x1 = (i + 1) * width / (ls - 1)
            y1 = (1.0 - self.points[i + 1]) * height

            if i < ls - 2:
                x_mid = i * width / (ls - 1) + width / (ls - 1) * 0.5
                y_mid = (y + y1) * 0.5
                points.extend([x_mid, y_mid, x1, y1])
            else:
                points.extend([x1, y1])

            x, y = x1, y1

        fill_points = points.copy()
        fill_points.extend([width, height, 0, height])

        segments = 30
        for i in range(segments):
            alpha = i / segments
            color = self.interpolate_color(self.colors, alpha)

            scaled_points = []
            for j in range(0, len(points), 2):
                x = points[j]
                y = points[j + 1]
                scaled_y = y + (height - y) * alpha * 0.3
                scaled_points.extend([x, scaled_y])

            scaled_points.extend([width, height, 0, height])

            if len(scaled_points) >= 6:
                try:
                    cr.set_source_rgba(color[0], color[1], color[2], 0.6 - alpha * 0.4)
                    cr.new_path()
                    cr.move_to(scaled_points[0], scaled_points[1])
                    for k in range(2, len(scaled_points), 2):
                        cr.line_to(scaled_points[k], scaled_points[k + 1])
                    cr.close_path()
                    cr.fill()
                except:
                    pass

        if len(points) >= 4:
            main_color = self.interpolate_color(self.colors, 0.5)
            cr.set_source_rgba(main_color[0], main_color[1], main_color[2], 0.9)
            cr.set_line_width(2)
            cr.new_path()
            cr.move_to(points[0], points[1])
            for i in range(2, len(points), 2):
                cr.line_to(points[i], points[i + 1])
            cr.stroke()

        return False

class ColorExtractor:
    @staticmethod
    def get_dominant_colors(image_input, num_colors=3):
        try:
            if isinstance(image_input, str):
                if image_input.startswith('http'):
                    response = requests.get(image_input, timeout=5)
                    image = Image.open(io.BytesIO(response.content))
                else:
                    image = Image.open(image_input)
            elif isinstance(image_input, (io.BytesIO, io.BufferedReader)):
                image_input.seek(0)
                image = Image.open(image_input)
            else:
                image = Image.open(image_input)

            image = image.resize((150, 150))
            image = image.convert('RGB')

            colors = image.getcolors(maxcolors=256*256*256)
            if not colors:
                return [(0.2, 0.3, 0.5), (0.4, 0.5, 0.7), (0.6, 0.7, 0.9)]

            colors.sort(key=lambda x: x[0], reverse=True)

            dominant_colors = []
            for count, color in colors[:num_colors]:
                r, g, b = [c/255.0 for c in color]
                dominant_colors.append((r, g, b))

            return dominant_colors

        except Exception as e:
            print(f"Error extracting colors: {e}")
            return [(0.2, 0.3, 0.5), (0.4, 0.5, 0.7), (0.6, 0.7, 0.9)]

    @staticmethod
    def generate_color_scheme(dominant_colors):
        primary = dominant_colors[0]
        h, s, v = colorsys.rgb_to_hsv(*primary)

        accent_h = (h + 0.3) % 1.0
        accent = colorsys.hsv_to_rgb(accent_h, s * 0.8, min(v + 0.2, 1.0))

        background_h = (h + 0.1) % 1.0
        background = colorsys.hsv_to_rgb(background_h, s * 0.4, v * 0.3)

        return {
            'primary': primary,
            'accent': accent,
            'background': background,
            'text': (1.0, 1.0, 1.0)
        }

class Config:
    def __init__(self):
        self.panel_icon = "view-media-track"
        self.use_album_cover_as_panel_icon = True
        self.fallback_to_icon_when_art_not_available = True
        self.album_cover_radius = 8
        self.choose_player_automatically = True
        self.preferred_player_identity = ""
        self.max_song_width_in_panel = 200
        self.skip_backward_control_in_panel = True
        self.play_pause_control_in_panel = True
        self.skip_forward_control_in_panel = True
        self.song_text_in_panel = True
        self.icon_in_panel = True
        self.text_scrolling_speed = 3
        self.text_scrolling_behaviour = 0
        self.pause_text_scrolling_while_media_is_not_playing = False
        self.text_scrolling_enabled = True
        self.text_scrolling_reset_on_pause = False
        self.volume_step = 5
        self.colors_from_album_cover = True
        self.panel_background_radius = 8
        self.fill_available_space = False
        self.panel_icon_size_ratio = 0.75
        self.panel_controls_size_ratio = 0.75
        self.title_position = 1
        self.artists_position = 1
        self.album_position = 0
        self.full_title_position = 1
        self.full_artists_position = 2
        self.full_album_position = 2
        self.full_view_text_scrolling_speed = 3
        self.no_media_text = "No media found"
        self.show_when_no_media = True
        self.visualizer_enabled = True

class MediaController:
    def __init__(self, config):
        self.config = config
        self.current_player = None
        self.players = {}
        self.last_error_time = 0
        self.error_cooldown = 5

        try:
            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SessionBus()
            self.setup_dbus_listeners()
            self.discover_players()
            print("D-Bus connection established")
        except Exception as e:
            print(f"D-Bus connection failed: {e}")
            self.bus = None

    def log_error(self, error_msg):
        current_time = time.time()
        if current_time - self.last_error_time > self.error_cooldown:
            print(f"Warning: {error_msg}")
            self.last_error_time = current_time

    def setup_dbus_listeners(self):
        if not self.bus:
            return

        try:
            self.bus.add_signal_receiver(
                self.on_properties_changed,
                signal_name='PropertiesChanged',
                dbus_interface='org.freedesktop.DBus.Properties',
                path='/org/mpris/MediaPlayer2'
            )

            self.bus.add_signal_receiver(
                self.on_name_owner_changed,
                signal_name='NameOwnerChanged',
                dbus_interface='org.freedesktop.DBus'
            )
        except Exception as e:
            self.log_error(f"Failed to setup D-Bus listeners: {e}")

    def discover_players(self):
        if not self.bus:
            return

        try:
            names = self.bus.list_names()
            found_players = []

            for name in names:
                if name.startswith('org.mpris.MediaPlayer2.'):
                    try:
                        self.add_player(name)
                        found_players.append(name.split('.')[-1])
                        if not self.current_player or self.config.choose_player_automatically:
                            self.current_player = name
                    except Exception as e:
                        self.log_error(f"Failed to add player {name}: {e}")

            if found_players:
                print(f"Found media players: {', '.join(found_players)}")
            else:
                print("No media players found. Start Spotify, VLC, or another MPRIS2 player.")

        except Exception as e:
            self.log_error(f"Error discovering players: {e}")

    def add_player(self, bus_name):
        if not self.bus:
            return

        try:
            player_obj = self.bus.get_object(bus_name, '/org/mpris/MediaPlayer2')

            props = dbus.Interface(player_obj, 'org.freedesktop.DBus.Properties')
            props.Get('org.mpris.MediaPlayer2', 'Identity')

            self.players[bus_name] = player_obj
            player_name = bus_name.split('.')[-1]
            print(f"Added player: {player_name}")

        except Exception as e:
            self.log_error(f"Failed to add player {bus_name}: {e}")

    def on_name_owner_changed(self, name, old_owner, new_owner):
        if name.startswith('org.mpris.MediaPlayer2.'):
            if new_owner:
                self.add_player(name)
                if not self.current_player or self.config.choose_player_automatically:
                    self.current_player = name
            elif old_owner and name in self.players:
                del self.players[name]
                if self.current_player == name:
                    self.current_player = next(iter(self.players), None)

    def on_properties_changed(self, interface, changed_properties, invalidated_properties):
        pass

    def safe_dbus_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except dbus.exceptions.DBusException as e:
            if "ServiceUnknown" in str(e):
                if self.current_player in self.players:
                    del self.players[self.current_player]
                    self.current_player = next(iter(self.players), None)
                    self.discover_players()
            else:
                self.log_error(f"D-Bus call failed: {e}")
            return None
        except Exception as e:
            self.log_error(f"Unexpected error in D-Bus call: {e}")
            return None

    def get_current_track_info(self):
        if not self.bus or not self.current_player or self.current_player not in self.players:
            return None

        try:
            player = self.players[self.current_player]
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')

            metadata = self.safe_dbus_call(
                props.Get, 'org.mpris.MediaPlayer2.Player', 'Metadata'
            )
            if not metadata:
                return None

            status = self.safe_dbus_call(
                props.Get, 'org.mpris.MediaPlayer2.Player', 'PlaybackStatus'
            )
            if not status:
                status = 'Stopped'

            track_info = {
                'title': str(metadata.get('xesam:title', 'Unknown Title')),
                'artist': ', '.join(metadata.get('xesam:artist', ['Unknown Artist'])),
                'album': str(metadata.get('xesam:album', 'Unknown Album')),
                'art_url': str(metadata.get('mpris:artUrl', '')),
                'status': str(status),
                'length': int(metadata.get('mpris:length', 0)) // 1000000,
            }

            position = self.safe_dbus_call(
                props.Get, 'org.mpris.MediaPlayer2.Player', 'Position'
            )
            track_info['position'] = int(position) // 1000000 if position else 0

            try:
                volume = self.safe_dbus_call(
                    props.Get, 'org.mpris.MediaPlayer2.Player', 'Volume'
                )
                track_info['volume'] = float(volume) if volume is not None else 0.5
            except:
                track_info['volume'] = 0.5

            shuffle = self.safe_dbus_call(
                props.Get, 'org.mpris.MediaPlayer2.Player', 'Shuffle'
            )
            track_info['shuffle'] = bool(shuffle) if shuffle is not None else False

            loop_status = self.safe_dbus_call(
                props.Get, 'org.mpris.MediaPlayer2.Player', 'LoopStatus'
            )
            track_info['loop_status'] = str(loop_status) if loop_status else 'None'

            return track_info

        except Exception as e:
            self.log_error(f"Error getting track info: {e}")
            return None

    def execute_player_action(self, action_name, *args):
        if not self.bus or not self.current_player or self.current_player not in self.players:
            print(f"No active player for action: {action_name}")
            return False

        try:
            player = self.players[self.current_player]
            player_interface = dbus.Interface(player, 'org.mpris.MediaPlayer2.Player')

            action_method = getattr(player_interface, action_name)
            result = self.safe_dbus_call(action_method, *args)

            if result is not None or action_name in ['PlayPause', 'Next', 'Previous']:
                print(f"Executed: {action_name}")
                return True
            else:
                print(f"Action may have failed: {action_name}")
                return False

        except AttributeError:
            self.log_error(f"Player doesn't support action: {action_name}")
            return False
        except Exception as e:
            self.log_error(f"Error executing {action_name}: {e}")
            return False

    def play_pause(self):
        return self.execute_player_action('PlayPause')

    def next_track(self):
        return self.execute_player_action('Next')

    def previous_track(self):
        return self.execute_player_action('Previous')

    def set_volume(self, volume):
        if not self.bus or not self.current_player or self.current_player not in self.players:
            return False

        try:
            player = self.players[self.current_player]
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')

            try:
                current_volume = props.Get('org.mpris.MediaPlayer2.Player', 'Volume')
                result = self.safe_dbus_call(
                    props.Set, 'org.mpris.MediaPlayer2.Player', 'Volume', dbus.Double(volume)
            )
                return result is not None
            except dbus.exceptions.DBusException as e:
                if "NotSupported" in str(e) or "Volume" in str(e):
                    return False
                else:
                    raise e

        except Exception as e:
            if "NotSupported" not in str(e):
                self.log_error(f"Error setting volume: {e}")
            return False

    def set_position(self, position):
        if not self.bus or not self.current_player or self.current_player not in self.players:
            return False

        try:
            player = self.players[self.current_player]
            player_interface = dbus.Interface(player, 'org.mpris.MediaPlayer2.Player')

            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')
            metadata = self.safe_dbus_call(props.Get, 'org.mpris.MediaPlayer2.Player', 'Metadata')

            track_id = dbus.ObjectPath('/')
            if metadata and 'mpris:trackid' in metadata:
                track_id = metadata['mpris:trackid']

            microseconds = dbus.Int64(position * 1000000)

            result = self.safe_dbus_call(player_interface.SetPosition, track_id, microseconds)

            if result is not None:
                print(f"Seeked to {position:.1f}s")
                return True
            else:
                current_pos = self.safe_dbus_call(props.Get, 'org.mpris.MediaPlayer2.Player', 'Position')
                if current_pos is not None:
                    offset = microseconds - current_pos
                    result = self.safe_dbus_call(player_interface.Seek, dbus.Int64(offset))
                    if result is not None:
                        print("Seeked using relative offset")
                        return True

                print("Both SetPosition and Seek failed")
                return False

        except Exception as e:
            self.log_error(f"Error setting position: {e}")
            return False

class LocalMusicPlayer:
    def __init__(self, callback=None):
        self.callback = callback
        self.current_file = None
        self.playlist = []
        self.current_index = 0
        self.play_order = "sequential"
        self.is_playing = False
        self.is_paused = False
        self.position = 0
        self.duration = 0
        self.volume = 0.5
        self.process = None
        self.supported_formats = ['.mp3', '.flac', '.ogg', '.m4a', '.wav']

    def load_directory(self, directory_path):
        self.playlist = []
        directory = Path(directory_path)

        for ext in self.supported_formats:
            files = list(directory.glob(f"**/*{ext}"))
            self.playlist.extend(files)

        self.playlist.sort()
        self.current_index = 0
        print(f"Loaded {len(self.playlist)} music files")
        return len(self.playlist) > 0

    def extract_metadata(self, file_path):
        try:
            file_path = str(file_path)
            audio_file = mutagen.File(file_path)

            if audio_file is None:
                return self._default_metadata(file_path)

            metadata = {
                'title': self._get_tag(audio_file, ['TIT2', 'TITLE', '\xa9nam']) or Path(file_path).stem,
                'artist': self._get_tag(audio_file, ['TPE1', 'ARTIST', '\xa9ART']) or 'Unknown Artist',
                'album': self._get_tag(audio_file, ['TALB', 'ALBUM', '\xa9alb']) or 'Unknown Album',
                'duration': getattr(audio_file, 'info', {}).length or 0,
                'art_data': None
            }

            if isinstance(audio_file, MP3):
                for tag in audio_file.tags.values():
                    if hasattr(tag, 'type') and tag.type == 3:
                        metadata['art_data'] = tag.data
                        break
            elif isinstance(audio_file, FLAC):
                if audio_file.pictures:
                    metadata['art_data'] = audio_file.pictures[0].data
            elif isinstance(audio_file, MP4):
                if 'covr' in audio_file:
                    metadata['art_data'] = audio_file['covr'][0]

            return metadata

        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
            return self._default_metadata(file_path)

    def _get_tag(self, audio_file, tag_names):
        for tag_name in tag_names:
            if tag_name in audio_file:
                value = audio_file[tag_name]
                if isinstance(value, list):
                    return str(value[0])
                return str(value)
        return None

    def _default_metadata(self, file_path):
        return {
            'title': Path(file_path).stem,
            'artist': 'Unknown Artist',
            'album': 'Unknown Album',
            'duration': 0,
            'art_data': None
        }

    def play_file(self, index=None):
        if not self.playlist:
            return False

        if index is not None:
            self.current_index = index

        if self.current_index >= len(self.playlist):
            self.current_index = 0

        self.current_file = self.playlist[self.current_index]

        self.stop()

        try:
            self.process = subprocess.Popen([
                'ffplay', '-nodisp', '-autoexit', '-volume', str(int(self.volume * 100)),
                str(self.current_file)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.is_playing = True
            self.is_paused = False
            self.position = 0

            metadata = self.extract_metadata(self.current_file)
            self.duration = metadata['duration']

            if self.callback:
                self.callback(metadata)

            print(f"Playing: {metadata['title']} by {metadata['artist']}")
            return True

        except FileNotFoundError:
            print("ffplay not found. Install with: sudo apt install ffmpeg")
            return False
        except Exception as e:
            print(f"Error playing file: {e}")
            return False

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.is_playing = False
        self.is_paused = False
        self.position = 0

    def pause(self):
        if self.is_playing and not self.is_paused:
            if self.process:
                self.process.terminate()
                self.process = None
            self.is_paused = True
            print(f"Paused at {self.position:.1f}s")
            return True
        elif self.is_paused:
            return self.resume_playback()
        return False

    def resume_playback(self):
        if not self.current_file:
            return False

        try:
            self.process = subprocess.Popen([
                'ffplay', '-nodisp', '-autoexit', '-volume', str(int(self.volume * 100)),
                '-ss', str(self.position),
                str(self.current_file)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.is_playing = True
            self.is_paused = False
            print(f"Resumed from {self.position:.1f}s")
            return True

        except Exception as e:
            print(f"Error resuming playback: {e}")
            return False

    def update_position(self):
        if self.is_playing and not self.is_paused and self.process and self.process.poll() is None:
            self.position += 0.1
            if self.duration > 0 and self.position >= self.duration:
                self.next_track()

    def next_track(self):
        if not self.playlist:
            return False

        if self.play_order == "shuffle":
            self.current_index = random.randint(0, len(self.playlist) - 1)
        elif self.play_order == "repeat_one":
            pass
        else:
            self.current_index += 1
            if self.current_index >= len(self.playlist):
                if self.play_order == "repeat_all":
                    self.current_index = 0
                else:
                    return False

        return self.play_file()

    def previous_track(self):
        if not self.playlist:
            return False

        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = len(self.playlist) - 1

        return self.play_file()

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))

        if self.is_playing and not self.is_paused and self.process:
            current_pos = self.position
            self.stop()
            self.position = current_pos
            if self.current_file:
                return self.resume_playback()

        return True

    def get_current_info(self):
        if not self.current_file:
            return None

        metadata = self.extract_metadata(self.current_file)

        art_url = ""
        if metadata['art_data']:
            art_hash = hashlib.md5(metadata['art_data']).hexdigest()
            if not hasattr(self, '_cached_art_hash') or self._cached_art_hash != art_hash:
                try:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    temp_file.write(metadata['art_data'])
                    temp_file.close()
                    self._cached_art_url = f"file://{temp_file.name}"
                    self._cached_art_hash = art_hash
                except:
                    pass
            art_url = getattr(self, '_cached_art_url', "")

        return {
            'title': metadata['title'],
            'artist': metadata['artist'],
            'album': metadata['album'],
            'art_url': art_url,
            'status': 'Playing' if self.is_playing and not self.is_paused else 'Paused',
            'length': int(metadata['duration']),
            'position': int(self.position),
            'volume': self.volume,
            'shuffle': self.play_order == "shuffle",
            'loop_status': 'Track' if self.play_order == "repeat_one" else 'Playlist' if self.play_order == "repeat_all" else 'None'
        }


class Ecliptic(Gtk.Window):
    def __init__(self):
        super().__init__()

        self.config = Config()

        self.media_controller = MediaController(self.config)
        self.current_track = None
        self.current_color_scheme = None
        self.last_art_url = ""
        self.background_surface = None
        self.is_seeking = False
        self.has_music_playing = False
        self.local_player = LocalMusicPlayer(callback=self.on_local_track_change)
        self.local_mode = False
        self.visualizer = None
        if self.config.visualizer_enabled:
            self.visualizer = CavaVisualizer(callback=self.on_visualizer_data)

        self.setup_window()
        self.setup_default_theme()
        self.setup_ui()

        GLib.timeout_add(100, self.update_display)

        self.connect("destroy", self.on_destroy)

        print("Ecliptic Music Player started")

    def on_visualizer_data(self, points):
        if hasattr(self, 'visualizer_widget') and self.visualizer_widget:
            self.visualizer_widget.set_points(points)
        return False

    def on_local_track_change(self, metadata):
        if metadata.get('art_data'):
            try:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                temp_file.write(metadata['art_data'])
                temp_file.close()
                art_url = f"file://{temp_file.name}"
                self.load_album_art_from_url(art_url)
            except Exception as e:
                print(f"Error loading local album art: {e}")

    def on_destroy(self, widget):
        if self.visualizer:
            self.visualizer.stop()
        Gtk.main_quit()

    def on_folder_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Music Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            folder_path = dialog.get_filename()
            if self.local_player.load_directory(folder_path):
                self.local_mode = True
                self.local_player.play_file(0)
            else:
                self.show_message("No music files found in the selected folder")

        dialog.destroy()

    def on_playlist_clicked(self, button):
        if not self.local_player.playlist:
            self.show_message("Load a music folder first")
            return

        dialog = Gtk.Dialog(title="Playlist & Playback Options", parent=self, modal=True)
        dialog.set_default_size(400, 500)

        content_area = dialog.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_left(15)
        content_area.set_margin_right(15)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)

        order_frame = Gtk.Frame(label="Playback Order")
        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        order_box.set_margin_left(10)
        order_box.set_margin_right(10)
        order_box.set_margin_top(5)
        order_box.set_margin_bottom(5)

        sequential_radio = Gtk.RadioButton.new_with_label(None, "Sequential")
        shuffle_radio = Gtk.RadioButton.new_with_label_from_widget(sequential_radio, "Shuffle")
        repeat_one_radio = Gtk.RadioButton.new_with_label_from_widget(sequential_radio, "Repeat One")
        repeat_all_radio = Gtk.RadioButton.new_with_label_from_widget(sequential_radio, "Repeat All")

        if self.local_player.play_order == "sequential":
            sequential_radio.set_active(True)
        elif self.local_player.play_order == "shuffle":
            shuffle_radio.set_active(True)
        elif self.local_player.play_order == "repeat_one":
            repeat_one_radio.set_active(True)
        elif self.local_player.play_order == "repeat_all":
            repeat_all_radio.set_active(True)

        order_box.pack_start(sequential_radio, False, False, 0)
        order_box.pack_start(shuffle_radio, False, False, 0)
        order_box.pack_start(repeat_one_radio, False, False, 0)
        order_box.pack_start(repeat_all_radio, False, False, 0)
        order_frame.add(order_box)
        content_area.pack_start(order_frame, False, False, 0)

        playlist_frame = Gtk.Frame(label="Playlist")
        playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 300)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        for i, file_path in enumerate(self.local_player.playlist):
            row = Gtk.ListBoxRow()

            song_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            song_box.set_margin_left(5)
            song_box.set_margin_right(5)
            song_box.set_margin_top(5)
            song_box.set_margin_bottom(5)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            metadata = self.local_player.extract_metadata(file_path)

            title_label = Gtk.Label(metadata['title'])
            title_label.set_halign(Gtk.Align.START)
            title_label.get_style_context().add_class("track-title")

            artist_label = Gtk.Label(f"{metadata['artist']} - {metadata['album']}")
            artist_label.set_halign(Gtk.Align.START)
            artist_label.get_style_context().add_class("track-artist")

            info_box.pack_start(title_label, False, False, 0)
            info_box.pack_start(artist_label, False, False, 0)

            song_box.pack_start(info_box, True, True, 0)

            if i == self.local_player.current_index:
                current_icon = Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.BUTTON)
                song_box.pack_start(current_icon, False, False, 0)

            row.add(song_box)
            row.song_index = i
            listbox.add(row)

        def on_song_selected(listbox, row):
            if row:
                self.local_player.play_file(row.song_index)
                dialog.response(Gtk.ResponseType.OK)

        listbox.connect("row-activated", on_song_selected)
        scrolled.add(listbox)
        playlist_box.pack_start(scrolled, True, True, 0)
        playlist_frame.add(playlist_box)
        content_area.pack_start(playlist_frame, True, True, 0)

        dialog.add_button("Apply", Gtk.ResponseType.APPLY)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            if sequential_radio.get_active():
                self.local_player.play_order = "sequential"
            elif shuffle_radio.get_active():
                self.local_player.play_order = "shuffle"
            elif repeat_one_radio.get_active():
                self.local_player.play_order = "repeat_one"
            elif repeat_all_radio.get_active():
                self.local_player.play_order = "repeat_all"
            print(f"Playback order set to: {self.local_player.play_order}")

        dialog.destroy()

    def show_message(self, message):
        dialog = Gtk.MessageDialog(
            parent=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

    def on_play_pause_clicked(self):
        if self.local_mode and self.local_player.playlist:
            self.local_player.pause()
        else:
            self.media_controller.play_pause()

    def on_previous_clicked(self, button=None):
        if self.local_mode and self.local_player.playlist:
            success = self.local_player.previous_track()
            print(f"Local player previous track: {success}")
            return
        self.media_controller.previous_track()

    def on_next_clicked(self, button=None):
        if self.local_mode and self.local_player.playlist:
            success = self.local_player.next_track()
            print(f"Local player next track: {success}")
            return
        self.media_controller.next_track()

    def setup_window(self):
        window_width = 520
        window_height = 810

        self.set_title("Ecliptic Music Player")
        self.set_default_size(window_width, window_height)
        self.set_size_request(window_width, window_height)
        self.set_resizable(False)

        self.set_decorated(True)

        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_skip_taskbar_hint(False)
        self.set_skip_pager_hint(False)

    def setup_ui(self):
        self.overlay = Gtk.Overlay()

        self.background_area = Gtk.DrawingArea()
        self.background_area.connect('draw', self.on_background_draw)
        self.overlay.add(self.background_area)

        self.setup_full_ui()

        self.overlay.add_overlay(self.main_container)

        self.add(self.overlay)

    def on_background_draw(self, widget, cr):
        allocation = widget.get_allocation()

        if self.background_surface and self.has_music_playing:
            cr.save()
            cr.scale(allocation.width / self.background_surface.get_width(),
                    allocation.height / self.background_surface.get_height())
            cr.set_source_surface(self.background_surface, 0, 0)
            cr.paint()
            cr.restore()

            cr.set_source_rgba(0, 0, 0, 0.15)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.fill()
        else:
            gradient = cairo.LinearGradient(0, 0, 0, allocation.height)
            gradient.add_color_stop_rgb(0, 0.2, 0.3, 0.5)
            gradient.add_color_stop_rgb(1, 0.1, 0.1, 0.2)
            cr.set_source(gradient)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.fill()

        return False

    def create_clean_background(self, art_url):
        if not art_url:
            return None

        try:
            image_data = None

            if art_url.startswith('file://'):
                file_path = art_url[7:]
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                else:
                    return None
            elif art_url.startswith(('http://', 'https://')):
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(art_url, timeout=10, headers=headers)
                response.raise_for_status()
                image_data = response.content
            else:
                if os.path.exists(art_url):
                    with open(art_url, 'rb') as f:
                        image_data = f.read()
                else:
                    return None

            if not image_data:
                return None

            pil_image = Image.open(io.BytesIO(image_data))

            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            target_width, target_height = 520, 810

            img_ratio = pil_image.width / pil_image.height
            target_ratio = target_width / target_height

            if img_ratio > target_ratio:
                new_height = pil_image.height
                new_width = int(new_height * target_ratio)
                left = (pil_image.width - new_width) // 2
                pil_image = pil_image.crop((left, 0, left + new_width, new_height))
            else:
                new_width = pil_image.width
                new_height = int(new_width / target_ratio)
                top = (pil_image.height - new_height) // 3
                pil_image = pil_image.crop((0, top, new_width, top + new_height))

            pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)

            pil_image = pil_image.filter(ImageFilter.GaussianBlur(radius=15))

            enhancer = ImageEnhance.Brightness(pil_image)
            pil_image = enhancer.enhance(0.7)

            width, height = pil_image.size
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)

            img_array = np.array(pil_image)

            buf = surface.get_data()
            buf_array = np.ndarray(shape=(height, width, 4), dtype=np.uint8, buffer=buf)

            buf_array[:, :, 0] = img_array[:, :, 2]
            buf_array[:, :, 1] = img_array[:, :, 1]
            buf_array[:, :, 2] = img_array[:, :, 0]
            buf_array[:, :, 3] = 255

            surface.mark_dirty()

            print(f"Created background surface: {width}x{height}")
            return surface

        except Exception as e:
            print(f"Error creating background: {e}")
            return None

    def load_album_art_from_url(self, art_url):
        if not art_url or art_url == self.last_art_url:
            return

        self.last_art_url = art_url

        def load_art_thread():
            try:
                image_data = None

                if art_url.startswith('file://'):
                    file_path = art_url[7:]
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            image_data = f.read()
                    else:
                        print(f"Local file not found: {file_path}")
                        GLib.idle_add(self.create_demo_album_art)
                        return
                elif art_url.startswith(('http://', 'https://')):
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    response = requests.get(art_url, timeout=10, headers=headers)
                    response.raise_for_status()
                    image_data = response.content
                else:
                    if os.path.exists(art_url):
                        with open(art_url, 'rb') as f:
                            image_data = f.read()
                    else:
                        print(f"Unsupported URL format or file not found: {art_url}")
                        GLib.idle_add(self.create_demo_album_art)
                        return

                if not image_data:
                    print(f"No image data loaded from: {art_url}")
                    GLib.idle_add(self.create_demo_album_art)
                    return

                loader = GdkPixbuf.PixbufLoader()
                loader.write(image_data)
                loader.close()

                pixbuf = loader.get_pixbuf()

                scaled_pixbuf = pixbuf.scale_simple(400, 400, GdkPixbuf.InterpType.BILINEAR)

                background_surface = self.create_clean_background(art_url)

                if self.config.colors_from_album_cover:
                    color_data = io.BytesIO(image_data)
                    dominant_colors = ColorExtractor.get_dominant_colors(color_data)
                    color_scheme = ColorExtractor.generate_color_scheme(dominant_colors)
                    GLib.idle_add(self.apply_color_scheme, color_scheme)

                GLib.idle_add(self.update_album_art_ui, scaled_pixbuf, background_surface)

            except Exception as e:
                print(f"Error loading album art: {e}")
                GLib.idle_add(self.create_demo_album_art)

        threading.Thread(target=load_art_thread, daemon=True).start()

    def update_album_art_ui(self, pixbuf, background_surface):
        self.album_art.set_from_pixbuf(pixbuf)

        self.background_surface = background_surface
        if hasattr(self, 'background_area'):
            self.background_area.queue_draw()

        if hasattr(self, 'visualizer_widget') and self.current_color_scheme:
            color = self.current_color_scheme.get('accent', (0.4, 0.5, 0.9))
            self.visualizer_widget.set_color(*color, 0.6)

        return False

    def setup_default_theme(self):
        self.apply_color_scheme({
            'primary': (0.4, 0.5, 0.9),
            'accent': (0.6, 0.7, 1.0),
            'background': (0.1, 0.1, 0.2),
            'text': (1.0, 1.0, 1.0)
        })

    def apply_color_scheme(self, color_scheme):
        self.current_color_scheme = color_scheme

        if hasattr(self, 'visualizer_widget') and self.visualizer_widget:
            accent_color = color_scheme.get('accent', (0.4, 0.5, 0.9))
            self.visualizer_widget.set_color(*accent_color, 0.6)

        def rgb_to_css(rgb):
            return f"rgb({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)})"

        primary_css = rgb_to_css(color_scheme['primary'])
        accent_css = rgb_to_css(color_scheme['accent'])
        bg_css = rgb_to_css(color_scheme['background'])

        css = f"""
        .ecliptic-window {{
            background: transparent;
            border-radius: 15px;
            color: white;
        }}

        .control-button.active {{
            background: rgba(255, 255, 255, 0.3);
            color: #FFD700;
        }}

        .album-art-shadow {{
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7);
            border-radius: 20px;
        }}

        .visualizer-container {{
            background: transparent;
            border-radius: 10px;
        }}

        .track-title {{
            font-size: 22px;
            font-weight: bold;
            color: white;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 1.0),
                         -1px -1px 2px rgba(0, 0, 0, 0.8),
                         1px -1px 2px rgba(0, 0, 0, 0.8),
                         -1px 1px 2px rgba(0, 0, 0, 0.8);
        }}

        .track-artist {{
            font-size: 16px;
            color: white;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 1.0),
                         -1px -1px 2px rgba(0, 0, 0, 0.8),
                         1px -1px 2px rgba(0, 0, 0, 0.8),
                         -1px 1px 2px rgba(0, 0, 0, 0.8);
        }}

        .control-button {{
            background: transparent;
            border: none;
            border-radius: 30px;
            color: white;
            min-width: 60px;
            min-height: 60px;
        }}

        .control-button:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .volume-slider {{
            color: white;
        }}

        .progress-bar {{
            background: transparent;
        }}

        .progress-bar trough {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 9px;
            min-height: 8px;
        }}

        .progress-bar slider {{
           background: transparent;
        border: none;
        box-shadow: none;
        min-width: 0;
        min-height: 0;
        margin: 0;
        padding: 0;
        opacity: 0;
        transition: none;
        }}

        .progress-bar:hover slider {{
            background: white;
        border: 8px solid #666;
        border-radius: 50%;
        min-width: 0px;
        min-height: 0px;
        opacity: 1;
        box-shadow: 0 0px 0px rgba(0,0,0,0.3);
        margin: -6px 0;
}}

        .volume-scale {{
            background: transparent;
        }}

        .volume-scale trough {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            min-height: 8px;
        }}

        .volume-scale slider {{
        background: transparent;
        border: none;
        box-shadow: none;
        min-width: 0;
        min-height: 0;
        margin: 0;
        padding: 0;
        opacity: 0;
        transition: none;
        }}

        .volume-scale:hover slider {{
        background: white;
        border: 8px solid #666;
        border-radius: 50%;
        min-width: 0px;
        min-height: 0px;
        opacity: 1;
        box-shadow: 0 0px 0px rgba(0,0,0,0.3);
        margin: -6px 0;
        }}
        """

        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.get_style_context().add_class("ecliptic-window")

    def setup_full_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_left(25)
        main_box.set_margin_right(25)
        main_box.set_margin_top(15)
        main_box.set_margin_bottom(15)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        local_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.folder_btn = Gtk.Button.new_from_icon_name("folder-music", Gtk.IconSize.BUTTON)
        self.folder_btn.set_tooltip_text("Load music folder")
        self.folder_btn.connect("clicked", self.on_folder_clicked)
        local_buttons_box.pack_start(self.folder_btn, False, False, 0)

        self.playlist_btn = Gtk.Button.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON)
        self.playlist_btn.set_tooltip_text("Playlist and playback options")
        self.playlist_btn.connect("clicked", self.on_playlist_clicked)
        local_buttons_box.pack_start(self.playlist_btn, False, False, 0)

        top_row.pack_start(local_buttons_box, False, False, 0)
        top_row.pack_start(Gtk.Label(), True, True, 0)

        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        volume_icon = Gtk.Image.new_from_icon_name("audio-volume-medium", Gtk.IconSize.LARGE_TOOLBAR)
        volume_box.pack_start(volume_icon, False, False, 0)

        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
        self.volume_scale.set_value(0.5)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_size_request(150, -1)
        self.volume_scale.connect("value-changed", self.on_volume_scale_changed)
        self.volume_scale.get_style_context().add_class("volume-scale")
        volume_box.pack_start(self.volume_scale, False, False, 0)

        top_row.pack_start(volume_box, False, False, 0)
        main_box.pack_start(top_row, False, False, 0)

        art_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        art_container.set_halign(Gtk.Align.CENTER)

        art_frame = Gtk.Frame()
        art_frame.get_style_context().add_class("album-art-shadow")
        art_frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.album_art = Gtk.Image()
        self.album_art.set_size_request(400, 400)
        art_frame.add(self.album_art)
        art_container.pack_start(art_frame, False, False, 0)
        self.create_demo_album_art()

        main_box.pack_start(art_container, False, False, 0)

        if self.config.visualizer_enabled:
            visualizer_frame = Gtk.Frame()
            visualizer_frame.get_style_context().add_class("visualizer-container")
            visualizer_frame.set_shadow_type(Gtk.ShadowType.NONE)

            self.visualizer_widget = VisualizerWidget()
            self.visualizer_widget.set_size_request(400, 80)
            visualizer_frame.add(self.visualizer_widget)

            visualizer_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            visualizer_container.set_halign(Gtk.Align.CENTER)
            visualizer_container.pack_start(visualizer_frame, False, False, 0)

            main_box.pack_start(visualizer_container, False, False, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info_box.set_halign(Gtk.Align.CENTER)

        self.title_label = Gtk.Label("No music detected")
        self.title_label.get_style_context().add_class("track-title")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_justify(Gtk.Justification.CENTER)
        self.title_label.set_line_wrap(True)
        self.title_label.set_max_width_chars(35)
        info_box.pack_start(self.title_label, False, False, 0)

        self.artist_label = Gtk.Label("Start playing music to see controls")
        self.artist_label.get_style_context().add_class("track-artist")
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_justify(Gtk.Justification.CENTER)
        self.artist_label.set_line_wrap(True)
        self.artist_label.set_max_width_chars(40)
        info_box.pack_start(self.artist_label, False, False, 0)

        main_box.pack_start(info_box, False, False, 0)

        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        self.progress_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.progress_scale.set_draw_value(False)
        self.progress_scale.connect("button-press-event", self.on_progress_click)
        self.progress_scale.connect("button-release-event", self.on_progress_release)
        self.progress_scale.connect("scroll-event", lambda w, e: True)
        self.progress_scale.get_style_context().add_class("progress-bar")
        progress_box.pack_start(self.progress_scale, False, False, 0)

        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.position_label = Gtk.Label("0:00")
        self.position_label.get_style_context().add_class("track-artist")
        time_box.pack_start(self.position_label, False, False, 0)

        time_box.pack_start(Gtk.Label(), True, True, 0)

        self.duration_label = Gtk.Label("0:00")
        self.duration_label.get_style_context().add_class("track-artist")
        time_box.pack_start(self.duration_label, False, False, 0)

        progress_box.pack_start(time_box, False, False, 0)
        main_box.pack_start(progress_box, False, False, 0)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        controls_box.set_halign(Gtk.Align.CENTER)

        self.shuffle_btn = Gtk.Button.new_from_icon_name("media-playlist-shuffle", Gtk.IconSize.LARGE_TOOLBAR)
        self.shuffle_btn.get_style_context().add_class("control-button")
        self.shuffle_btn.connect("clicked", self.on_shuffle_clicked)
        controls_box.pack_start(self.shuffle_btn, False, False, 0)

        prev_btn = Gtk.Button.new_from_icon_name("media-skip-backward", Gtk.IconSize.LARGE_TOOLBAR)
        prev_btn.get_style_context().add_class("control-button")
        prev_btn.connect("clicked", lambda x: self.on_previous_clicked())
        controls_box.pack_start(prev_btn, False, False, 0)

        self.play_pause_btn = Gtk.Button.new_from_icon_name("media-playback-start", Gtk.IconSize.DIALOG)
        self.play_pause_btn.get_style_context().add_class("control-button")
        self.play_pause_btn.connect("clicked", lambda x: self.on_play_pause_clicked())
        controls_box.pack_start(self.play_pause_btn, False, False, 0)

        next_btn = Gtk.Button.new_from_icon_name("media-skip-forward", Gtk.IconSize.LARGE_TOOLBAR)
        next_btn.get_style_context().add_class("control-button")
        next_btn.connect("clicked", lambda x: self.on_next_clicked())
        controls_box.pack_start(next_btn, False, False, 0)

        self.repeat_btn = Gtk.Button.new_from_icon_name("media-playlist-repeat", Gtk.IconSize.LARGE_TOOLBAR)
        self.repeat_btn.get_style_context().add_class("control-button")
        self.repeat_btn.connect("clicked", self.on_repeat_clicked)
        controls_box.pack_start(self.repeat_btn, False, False, 0)

        main_box.pack_start(controls_box, False, False, 0)

        self.main_container = main_box

    def on_progress_click(self, scale, event):
        self.is_seeking = True
        return False

    def on_progress_release(self, scale, event):
        if self.is_seeking:
            value = scale.get_value()

            if self.local_mode and self.local_player.current_file:
                track_info = self.local_player.get_current_info()
                if track_info and track_info['length'] > 0:
                    position = (value / 100) * track_info['length']
                    self.local_player.position = position
                    if self.local_player.is_playing and not self.local_player.is_paused:
                        self.local_player.stop()
                        self.local_player.position = position
                        self.local_player.resume_playback()
                    print(f"Local seek to {value:.1f}% ({position:.1f}s)")
            else:
                track_info = self.media_controller.get_current_track_info()
                if track_info and track_info['length'] > 0:
                    position = (value / 100) * track_info['length']
                    if self.media_controller.set_position(position):
                        print(f"Seeked to {value:.1f}% ({position:.1f}s)")
                    else:
                        print("Seek failed")

            self.is_seeking = False
        return False

    def on_volume_scale_changed(self, scale):
        value = scale.get_value()
        if self.local_mode and self.local_player:
            self.local_player.set_volume(value)
            print(f"Local volume set to {value:.0%}")
        elif self.media_controller.set_volume(value):
            print(f"Volume set to {value:.0%}")

    def on_shuffle_clicked(self, button):
        if self.local_mode and self.local_player:
            if self.local_player.play_order == "shuffle":
                self.local_player.play_order = "sequential"
                print("Local shuffle disabled")
            else:
                self.local_player.play_order = "shuffle"
                print("Local shuffle enabled")
            return

        if not self.media_controller.bus or not self.media_controller.current_player or self.media_controller.current_player not in self.media_controller.players:
            return

        try:
            player = self.media_controller.players[self.media_controller.current_player]
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')

            current_shuffle = self.media_controller.safe_dbus_call(props.Get, 'org.mpris.MediaPlayer2.Player', 'Shuffle')
            new_shuffle = not bool(current_shuffle) if current_shuffle is not None else True

            result = self.media_controller.safe_dbus_call(props.Set, 'org.mpris.MediaPlayer2.Player', 'Shuffle', dbus.Boolean(new_shuffle))

            if result is not None:
                print(f"Shuffle {'enabled' if new_shuffle else 'disabled'}")
            else:
                print("Shuffle toggle failed")

        except Exception as e:
            print(f"Error toggling shuffle: {e}")

    def on_repeat_clicked(self, button):
        if self.local_mode and self.local_player:
            if self.local_player.play_order == "sequential":
                self.local_player.play_order = "repeat_one"
                print("Local repeat: Track")
            elif self.local_player.play_order == "repeat_one":
                self.local_player.play_order = "repeat_all"
                print("Local repeat: Playlist")
            else:
                self.local_player.play_order = "sequential"
                print("Local repeat: Off")
            return

        if not self.media_controller.bus or not self.media_controller.current_player or self.media_controller.current_player not in self.media_controller.players:
            return

        try:
            player = self.media_controller.players[self.media_controller.current_player]
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')

            current_loop = self.media_controller.safe_dbus_call(props.Get, 'org.mpris.MediaPlayer2.Player', 'LoopStatus')
            current_loop = str(current_loop) if current_loop else 'None'

            if current_loop == 'None':
                new_loop = 'Track'
            elif current_loop == 'Track':
                new_loop = 'Playlist'
            else:
                new_loop = 'None'

            result = self.media_controller.safe_dbus_call(props.Set, 'org.mpris.MediaPlayer2.Player', 'LoopStatus', dbus.String(new_loop))

            if result is not None:
                print(f"Repeat mode: {new_loop}")
            else:
                print("Repeat toggle failed")

        except Exception as e:
            print(f"Error toggling repeat: {e}")

    def create_demo_album_art(self):
        size = 320
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surface)

        if self.current_color_scheme:
            primary = self.current_color_scheme['primary']
            accent = self.current_color_scheme['accent']
        else:
            primary = (0.3, 0.5, 0.9)
            accent = (0.6, 0.7, 1.0)

        gradient = cairo.LinearGradient(0, 0, size, size)
        gradient.add_color_stop_rgb(0, *primary)
        gradient.add_color_stop_rgb(1, *accent)
        cr.set_source(gradient)
        cr.rectangle(0, 0, size, size)
        cr.fill()

        cr.set_source_rgb(1, 1, 1)
        note_scale = size / 150.0
        cr.set_line_width(8 * note_scale)
        cr.arc(size/2, size*0.6, 20*note_scale, 0, 2 * math.pi)
        cr.stroke()
        cr.move_to(size/2 + 20*note_scale, size*0.6)
        cr.line_to(size/2 + 20*note_scale, size*0.33)
        cr.stroke()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(16 * note_scale)
        text_width = cr.text_extents("Ecliptic")[2]
        cr.move_to((size - text_width) / 2, size*0.8)
        cr.show_text("Ecliptic")

        buf = surface.get_data()
        img_array = np.ndarray(shape=(size, size, 4), dtype=np.uint8, buffer=buf)
        img_array = img_array[:, :, [2, 1, 0, 3]]

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            img_array.tobytes(),
            GdkPixbuf.Colorspace.RGB,
            True, 8, size, size, size * 4
        )

        self.album_art.set_from_pixbuf(pixbuf)

    def format_time(self, seconds):
        if seconds is None or seconds < 0:
            return "0:00"
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"

    def update_display(self):
        if self.local_mode and self.local_player:
            self.local_player.update_position()

        if self.local_mode and self.local_player.current_file:
            track_info = self.local_player.get_current_info()
        else:
            track_info = self.media_controller.get_current_track_info()

        if track_info:
            self.has_music_playing = track_info['status'] in ['Playing', 'Paused']

            if self.visualizer and self.config.visualizer_enabled:
                if track_info['status'] == 'Playing' and not self.visualizer.running:
                    self.visualizer.start()
                elif track_info['status'] != 'Playing' and self.visualizer.running:
                    self.visualizer.stop()

            if track_info.get('art_url') and track_info['art_url'] != self.last_art_url:
                print(f"Loading new album art: {track_info['art_url']}")
                self.load_album_art_from_url(track_info['art_url'])
            elif not track_info.get('art_url') and self.last_art_url:
                print("Clearing album art background")
                self.last_art_url = ""
                self.background_surface = None
                if hasattr(self, 'background_area'):
                    self.background_area.queue_draw()

            title_text = track_info['title']
            artist_text = track_info['artist']

            self.title_label.set_text(title_text)
            self.artist_label.set_text(artist_text)

            if not self.is_seeking and track_info['length'] > 0:
                progress = (track_info['position'] / track_info['length']) * 100
                self.progress_scale.set_value(progress)

            self.position_label.set_text(self.format_time(track_info['position']))
            self.duration_label.set_text(self.format_time(track_info['length']))

            if track_info['status'] == 'Playing':
                self.play_pause_btn.set_image(
                    Gtk.Image.new_from_icon_name("media-playback-pause", Gtk.IconSize.DIALOG)
                )
            else:
                self.play_pause_btn.set_image(
                    Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.DIALOG)
                )

            self.volume_scale.set_value(track_info.get('volume', 0.5))

            if hasattr(self, 'shuffle_btn'):
                if track_info.get('shuffle'):
                    self.shuffle_btn.get_style_context().add_class("active")
                else:
                    self.shuffle_btn.get_style_context().remove_class("active")

            if hasattr(self, 'repeat_btn'):
                loop_status = track_info.get('loop_status', 'None')
                if loop_status != 'None':
                    self.repeat_btn.get_style_context().add_class("active")
                    if loop_status == 'Track':
                        self.repeat_btn.set_image(Gtk.Image.new_from_icon_name("media-playlist-repeat-song", Gtk.IconSize.LARGE_TOOLBAR))
                    else:
                        self.repeat_btn.set_image(Gtk.Image.new_from_icon_name("media-playlist-repeat", Gtk.IconSize.LARGE_TOOLBAR))
                else:
                    self.repeat_btn.get_style_context().remove_class("active")
                    self.repeat_btn.set_image(Gtk.Image.new_from_icon_name("media-playlist-repeat", Gtk.IconSize.LARGE_TOOLBAR))

        else:
            self.has_music_playing = False

            if self.visualizer and self.visualizer.running:
                self.visualizer.stop()

            self.title_label.set_text(self.config.no_media_text)
            self.artist_label.set_text("Start playing music to see controls")
            if not self.is_seeking:
                self.progress_scale.set_value(0)
            self.position_label.set_text("0:00")
            self.duration_label.set_text("0:00")
            self.play_pause_btn.set_image(
                Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.DIALOG)
            )

        if hasattr(self, 'background_area'):
            self.background_area.queue_draw()

        return True

def main():
    parser = argparse.ArgumentParser(description='Ecliptic Music Player with Cava Visualizer')
    parser.add_argument('--no-visualizer', action='store_true', help='Disable audio visualizer')

    args = parser.parse_args()

    print("Starting Ecliptic Music Player...")

    def signal_handler(sig, frame):
        print("Ecliptic Music Player stopped by user")
        Gtk.main_quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app = Ecliptic()

    if args.no_visualizer:
        app.config.visualizer_enabled = False
        if app.visualizer:
            app.visualizer.stop()
            app.visualizer = None
        print("Audio visualizer disabled")

    app.connect("destroy", Gtk.main_quit)
    app.show_all()

    print("Ecliptic Music Player window opened")
    print("Features:")
    print("   Cava audio visualizer with real-time frequency bars")
    print("   Smooth waveform visualization that responds to music")
    print("   Visualizer color adapts to album art theme")
    print("   Larger window (520x810 pixels) for bigger UI elements")
    print("   Much larger album art (400x400 pixels)")
    print("   Dynamic color themes from album art")
    print("   Enhanced album art with larger shadow effects")
    print("   Bigger media controls and buttons")
    print("   Volume control moved to top for better layout")
    print("   Enhanced progress bars with bigger sliders")
    print("   Text and controls repositioned below album art")
    print("   Always white text with black borders/shadows for readability")
    print("   Transparent buttons with white hover background")
    print("   Improved D-Bus error handling")
    print("   Reorganized layout to prevent overlapping")
    print("   Audio visualizer positioned between album art and song info")
    print("")
    print("Visualizer Features:")
    print("   60 frequency bars with smooth transitions")
    print("   Color adapts to album art dominant colors")
    print("   Automatic start/stop based on playback status")
    print("   Real-time audio analysis with cava")
    print("   Smooth bar transitions and mirrored visualization")
    print("")
    print("Instructions:")
    print("   1. Play music in Spotify, VLC, Firefox, or any MPRIS2 player")
    print("   2. Album art creates a clean, recognizable background")
    print("   3. Audio visualizer shows real-time frequency analysis")
    print("   4. Visualizer automatically starts when music plays")
    print("   5. Album art now dominates the interface (about half the window)")
    print("   6. All controls repositioned below album art for no overlap")
    print("   7. Click progress bar to seek, use volume controls")
    print("   8. Interface colors and visualizer adapt to album art")
    print("   9. Volume control moved to top for clean layout")
    print("   10. Perfect for high DPI displays or better visibility")
    print("   11. Hover over progress/volume sliders to see controls")
    print("")
    print("Available modes:")
    print("   python3 ecliptic.py                       # Full player window (default)")
    print("   python3 ecliptic.py --no-visualizer       # Disable audio visualizer")
    print("")
    print("Required dependencies:")
    print("   pip install pillow requests numpy dbus-python")
    print("   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 cava")
    print("")
    print("Troubleshooting:")
    print("   - Install cava: sudo apt install cava (for Ubuntu/Debian)")
    print("   - For Arch: sudo pacman -S cava")
    print("   - For Fedora: sudo dnf install cava")
    print("   - If buttons don't work: Check if media player supports MPRIS2")
    print("   - If no album art: Check internet connection")
    print("   - If visualizer doesn't work: Ensure cava is installed and audio is playing")
    print("   - D-Bus errors are normal and handled gracefully")
    print("   - Window should float automatically in Hyprland")
    print("   - Album art now takes up about half the window space")
    print("   - All UI elements repositioned to prevent overlapping")
    print("   - Visualizer shows between album art and song info")

    try:
        Gtk.main()
    except KeyboardInterrupt:
        print("Ecliptic Music Player with Visualizer stopped by user")
    finally:
        if hasattr(app, 'visualizer') and app.visualizer:
            app.visualizer.stop()

if __name__ == "__main__":
    main()
