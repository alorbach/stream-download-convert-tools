# audiotools

Unified audio and video tools for downloading and processing content from YouTube.

## Features

### Audio Tools - Unified Application
A single graphical application with tabbed interface containing three powerful tools:

#### YouTube Downloader Tab
- Load CSV files containing YouTube links
- Command-line support for auto-loading CSV files on startup
- View all available video/audio streams with quality information
- Select specific formats (video+audio, video only, or audio only)
- Customize output filenames using CSV field data
- Real-time download progress with console output display
- Visual progress bar and wait cursor during operations

#### Video to MP3 Converter Tab
- Select multiple video/audio files (MP4, WEBM, M4A, AVI, MOV, MKV, FLV, WMV)
- Batch conversion with progress tracking
- Configurable audio quality (128k, 192k, 256k, 320k)
- Automatic output to converted folder with same basename
- Real-time conversion log
- Uses FFmpeg for high-quality conversion

#### Audio Modifier Tab
- Modify MP3, M4A, WAV, OGG, FLAC files
- Speed adjustment: -50% to +100% (tempo change without pitch change)
- Pitch adjustment: -12 to +12 semitones (change pitch without tempo change)
- Quick preset buttons for common modifications
- Batch processing with progress tracking
- Configurable audio quality (128k, 192k, 256k, 320k)
- Automatic output to converted_changed folder with descriptive suffixes
- Real-time modification log
- Uses FFmpeg for high-quality audio processing

#### Settings Tab
- Configure download folder location
- Customize filename patterns for YouTube downloads
- Centralized settings management

### Key Benefits of Unified Application
- Single application to launch instead of three separate tools
- Seamless workflow between downloading, converting, and modifying
- Shared FFmpeg installation and management
- Consistent user interface across all tools
- Automatic virtual environment management
- Cross-platform support (Windows, Linux, Mac)

## Requirements

- Python 3.7 or higher
- Internet connection for downloading YouTube videos
- FFmpeg (required for video to MP3 conversion)
  - Windows: Automatically downloaded when first needed (no admin rights required)
  - Linux: `sudo apt-get install ffmpeg`
  - Mac: `brew install ffmpeg`

## Installation & Usage

### Windows

1. **Launch Unified Application**: Double-click `launchers/audio_tools_unified.bat`
   - First run will automatically create virtual environment and install dependencies
   - Subsequent runs will launch directly

2. **Auto-load CSV**: Drag and drop a CSV file onto the launcher, or:
   ```cmd
   launchers\audio_tools_unified.bat input\top100.csv
   ```

### Linux/Mac

1. Make the launcher executable (first time only):
   ```bash
   chmod +x launchers/audio_tools_unified.sh
   ```

2. **Basic Launch**:
   ```bash
   ./launchers/audio_tools_unified.sh
   ```

3. **Auto-load CSV**:
   ```bash
   ./launchers/audio_tools_unified.sh input/top100.csv
   ```

### Legacy Individual Tools (Still Available)

The original individual tools are still available for users who prefer separate applications:

**Windows:**
- `launchers/youtube_downloader.bat` - YouTube downloader only
- `launchers/video_to_mp3_converter.bat` - Video to MP3 converter only  
- `launchers/audio_modifier.bat` - Audio modifier only

**Linux/Mac:**
- `launchers/youtube_downloader.sh` - YouTube downloader only
- `launchers/video_to_mp3_converter.sh` - Video to MP3 converter only
- `launchers/audio_modifier.sh` - Audio modifier only

## How to Use Audio Tools - Unified

### YouTube Downloader Tab

1. **Load CSV File**
   - Click "Select CSV File" and choose your CSV file
   - Preview will show the file contents
   - Sample file: `input/top100.csv`

2. **Select Video**
   - Select a video from the list
   - Click "Fetch Available Streams"

3. **Choose Stream**
   - Browse available streams organized by type:
     - Video + Audio: Complete files ready to play
     - Video Only: Video without audio track
     - Audio Only: Audio files (MP3, M4A, etc.)
   - View quality, file size, and codec information
   - Select your preferred stream

4. **Download**
   - Click "Download Selected Stream"
   - Watch the progress bar and wait cursor while downloading
   - Real-time console output appears in the log window
   - Files are saved to the `downloads/` folder

### Video to MP3 Converter Tab

1. **Select Video/Audio Files**
   - Click "Select Video Files"
   - Choose one or more video/audio files (MP4, WEBM, M4A, etc.)
   - Files will appear in the selection list
   - Default folder: `downloads/` (where YouTube videos are saved)

2. **Configure Settings** (Optional)
   - Choose output folder (default: `converted/`)
   - Select audio quality: 128k, 192k, 256k, or 320k
   - Higher quality = larger file size

3. **Convert to MP3**
   - Click "Convert to MP3"
   - Progress bar shows conversion progress
   - Log window displays detailed conversion information
   - Output files saved with same basename as input

### Audio Modifier Tab

1. **Select Audio Files**
   - Click "Select Audio Files"
   - Choose one or more audio files (MP3, M4A, WAV, OGG, FLAC)
   - Files will appear in the selection list
   - Default folder: `converted/` (where MP3 files are saved)

2. **Configure Modifications**
   - **Speed Adjustment**: -50% to +100%
     - Negative values slow down the audio
     - Positive values speed up the audio
     - Changes tempo without affecting pitch
   - **Pitch Adjustment**: -12 to +12 semitones
     - Negative values lower the pitch
     - Positive values raise the pitch
     - 12 semitones = 1 octave
     - Changes pitch without affecting tempo
   - **Audio Quality**: Select 128k, 192k, 256k, or 320k

3. **Use Quick Presets** (Optional)
   - Slower -10%: Reduce speed by 10%
   - Faster +10%: Increase speed by 10%
   - Pitch -1: Lower pitch by 1 semitone
   - Pitch +1: Raise pitch by 1 semitone
   - Reset: Set both to 0 (no change)

4. **Modify Audio Files**
   - Click "Modify Audio Files"
   - Progress bar shows modification progress
   - Log window displays detailed processing information
   - Output files are saved with descriptive suffixes

### Settings Tab

1. **Configure Download Settings**
   - Change download folder location
   - Customize filename pattern using CSV fields:
     - `{Rank}` - Rank number
     - `{Song Title}` - Song title
     - `{Artist}` - Artist name
     - `{Year}` - Year
     - `{Views (Billions)}` - View count
   - Default pattern: `{Rank}_{Song Title}_{Artist}`

## Recommended Workflow

1. **Download Videos**: Use the YouTube Downloader tab to download videos from CSV lists
2. **Convert to MP3**: Use the Video to MP3 Converter tab to extract audio from downloaded videos
3. **Modify Audio**: Use the Audio Modifier tab to adjust speed and pitch as needed

## FFmpeg Setup (First Time Only)

- **Windows**: If FFmpeg is not found, the app will offer to download it automatically
  - Click "Yes" to download (approximately 80MB, no admin rights needed)
- **Linux/Mac**: Install FFmpeg using the command shown in the prompt:
  - Linux: `sudo apt-get install ffmpeg`
  - Mac: `brew install ffmpeg`

## Examples

### Audio Modification Examples
- **Slow down a song by 10%**: Speed = -10%, Pitch = 0
- **Speed up a song by 20%**: Speed = 20%, Pitch = 0
- **Lower pitch by 1 semitone**: Speed = 0%, Pitch = -1
- **Raise pitch by 2 semitones**: Speed = 0%, Pitch = 2
- **Slow down AND lower pitch**: Speed = -10%, Pitch = -2
- **Speed up AND raise pitch**: Speed = 15%, Pitch = 1

## CSV File Format

Your CSV file should contain YouTube links. The downloader supports:
- Direct URLs: `https://www.youtube.com/watch?v=VIDEO_ID`
- Markdown format: `[https://www.youtube.com/watch?v=VIDEO_ID](https://www.youtube.com/watch?v=VIDEO_ID)`
- Search URLs: `https://www.youtube.com/results?search_query=Artist+-+Song+Title`

Example CSV structure (from `input/top100.csv`):
```csv
"Rank","Song Title","Artist","Views (Billions)","Year","Video Link"
1,"Despacito","Luis Fonsi ft. Daddy Yankee",8.82,2017,"[https://www.youtube.com/watch?v=kJQP7kiw5Fk](https://www.youtube.com/watch?v=kJQP7kiw5Fk)"
```

## Project Structure

```
audiotools/
├── venv/                                # Virtual environment (auto-created)
├── input/                               # Input CSV files
│   └── top100.csv                      # Sample YouTube links
├── downloads/                           # Downloaded videos (auto-created)
├── converted/                           # Converted MP3 files (auto-created)
├── converted_changed/                   # Modified audio files (auto-created)
├── ffmpeg/                              # FFmpeg portable (Windows, auto-downloaded)
├── scripts/                             # Python scripts
│   ├── audio_tools_unified.py          # Unified application (RECOMMENDED)
│   ├── youtube_downloader.py           # Individual YouTube downloader
│   ├── video_to_mp3_converter.py       # Individual Video to MP3 converter
│   └── audio_modifier.py               # Individual Audio modifier
├── launchers/                           # Launcher scripts
│   ├── audio_tools_unified.bat         # Windows launcher (Unified - RECOMMENDED)
│   ├── audio_tools_unified.sh          # Linux/Mac launcher (Unified - RECOMMENDED)
│   ├── youtube_downloader.bat          # Windows launcher (YouTube only)
│   ├── youtube_downloader.sh           # Linux/Mac launcher (YouTube only)
│   ├── video_to_mp3_converter.bat      # Windows launcher (Converter only)
│   ├── video_to_mp3_converter.sh       # Linux/Mac launcher (Converter only)
│   ├── audio_modifier.bat              # Windows launcher (Audio Modifier only)
│   └── audio_modifier.sh               # Linux/Mac launcher (Audio Modifier only)
├── requirements.txt                     # Python dependencies
├── .gitignore                           # Git ignore rules
├── AGENT.md                             # Developer/agent documentation
└── README.md                            # This file
```

## Advanced Features

### Auto-loading CSV Files
You can auto-load a CSV file on startup:
- **Windows**: Drag and drop CSV file onto `audio_tools_unified.bat`
- **Command line**: Pass CSV file path as first argument to launcher
- The GUI will automatically load the CSV and display the video list in the YouTube Downloader tab

### Console Output Integration
All operations show detailed console-style output in the GUI log window:
- `[INFO]` - Informational messages
- `[SUCCESS]` - Successful operations
- `[ERROR]` - Error messages
- Real-time yt-dlp download progress

### Visual Feedback
- **Progress bar**: Animated progress indicator during operations
- **Wait cursor**: Mouse cursor changes to waiting state during busy operations
- **Status messages**: Current operation displayed above progress bar

## Troubleshooting

### Virtual Environment Issues
If you encounter venv problems:
1. Delete the `venv/` folder
2. Re-run the launcher script

### Download Failures
If downloads fail:
1. Check your internet connection
2. Verify the YouTube URL is valid
3. Update yt-dlp: The launcher auto-updates dependencies
4. Some videos may be geo-restricted or require authentication

### Conversion Failures
If MP3 conversion fails:
1. Ensure FFmpeg is installed and in system PATH
2. Check that video files are not corrupted
3. Try a different audio quality setting
4. Verify sufficient disk space in output folder

### GUI Not Showing
Ensure tkinter is installed with Python:
- Windows: Included by default
- Linux: Install with `sudo apt-get install python3-tk`
- Mac: Included by default

### FFmpeg Not Found
**Windows**: The application will offer to download FFmpeg automatically (portable version, no admin rights needed).

**Linux/Mac**: If you get "FFmpeg not found" error:
1. Install FFmpeg using the command shown in the error message
2. Restart the application
3. Test: Open terminal and type `ffmpeg -version`

**Manual Installation (all platforms)**:
1. Download from https://ffmpeg.org/download.html
2. Add to system PATH, or place in `ffmpeg/bin/` folder within the project

## Notes

- All launchers automatically manage virtual environments
- Downloaded files are saved to `downloads/` folder by default
- Converted MP3 files are saved to `converted/` folder by default
- Modified audio files are saved to `converted_changed/` folder by default
- The unified application uses `yt-dlp` for YouTube downloading (actively maintained)
- All processing uses FFmpeg for high-quality audio/video operations
- Filename patterns sanitize special characters automatically
- Original video and audio files are never modified or deleted during processing
- **Recommended**: Use the unified application (`audio_tools_unified`) for the best experience
- **Legacy**: Individual tools remain available for users who prefer separate applications

## Legal Disclaimer

This software is provided for educational and personal use only. Users are responsible for:
- Complying with applicable copyright laws in their jurisdiction
- Respecting YouTube's Terms of Service
- Only downloading content they have legal rights to access
- Understanding fair use guidelines for their intended use

**Important**: This tool does not circumvent any digital rights management (DRM) or access controls. Users must ensure their use complies with all applicable laws and platform terms of service.

The authors disclaim any responsibility for misuse of this software.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## Documentation

- **User Guide**: See [USER_GUIDE.md](USER_GUIDE.md) for comprehensive tutorials and usage instructions
- **Developer Guide**: See `AGENT.md` for detailed development guidelines and project architecture
