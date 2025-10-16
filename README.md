# audiotools

Audio and video tools for downloading and processing content from YouTube.

## Features

### YouTube Downloader (GUI)
A graphical application for downloading YouTube videos with advanced features:
- Load CSV files containing YouTube links
- Command-line support for auto-loading CSV files on startup
- View all available video/audio streams with quality information
- Select specific formats (video+audio, video only, or audio only)
- Customize output filenames using CSV field data
- Real-time download progress with console output display
- Visual progress bar and wait cursor during operations
- Automatic virtual environment management

### Video to MP3 Converter (GUI)
A graphical application for converting video/audio files to MP3 format:
- Select multiple video/audio files (MP4, WEBM, M4A, AVI, MOV, MKV, FLV, WMV)
- Batch conversion with progress tracking
- Configurable audio quality (128k, 192k, 256k, 320k)
- Automatic output to converted folder with same basename
- Real-time conversion log
- Uses FFmpeg for high-quality conversion
- Automatic FFmpeg installation on Windows (no admin rights needed)

## Requirements

- Python 3.7 or higher
- Internet connection for downloading YouTube videos
- FFmpeg (required for video to MP3 conversion)
  - Windows: Automatically downloaded when first needed (no admin rights required)
  - Linux: `sudo apt-get install ffmpeg`
  - Mac: `brew install ffmpeg`

## Installation & Usage

### Windows

1. **Basic Launch**: Double-click `launchers/youtube_downloader.bat`
   - First run will automatically create virtual environment and install dependencies
   - Subsequent runs will launch directly

2. **Auto-load CSV**: Drag and drop a CSV file onto the launcher, or:
   ```cmd
   launchers\youtube_downloader.bat input\top100.csv
   ```

3. **Launch Video to MP3 Converter**: Double-click `launchers/video_to_mp3_converter.bat`

### Linux/Mac

1. Make the launcher executable (first time only):
   ```bash
   chmod +x launchers/youtube_downloader.sh
   chmod +x launchers/video_to_mp3_converter.sh
   ```

2. **Basic Launch**:
   ```bash
   ./launchers/youtube_downloader.sh
   ```

3. **Auto-load CSV**:
   ```bash
   ./launchers/youtube_downloader.sh input/top100.csv
   ```

4. **Launch Video to MP3 Converter**:
   ```bash
   ./launchers/video_to_mp3_converter.sh
   ```

## How to Use YouTube Downloader

1. **Load CSV File**
   - Go to "Load CSV" tab
   - Click "Select CSV File" and choose your CSV file
   - Preview will show the file contents
   - Sample file: `input/top100.csv`

2. **Select Video**
   - Go to "Download Videos" tab
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

5. **Configure Settings** (Optional)
   - Go to "Settings" tab
   - Change download folder location
   - Customize filename pattern using CSV fields:
     - `{Rank}` - Rank number
     - `{Song Title}` - Song title
     - `{Artist}` - Artist name
     - `{Year}` - Year
     - `{Views (Billions)}` - View count
   - Default pattern: `{Rank}_{Song Title}_{Artist}`

## How to Use Video to MP3 Converter

1. **Launch the Application**
   - Windows: Double-click `launchers/video_to_mp3_converter.bat`
   - Linux/Mac: Run `./launchers/video_to_mp3_converter.sh`

2. **FFmpeg Setup (First Time Only)**
   - Windows: If FFmpeg is not found, the app will offer to download it automatically
   - Click "Yes" to download (approximately 80MB, no admin rights needed)
   - Linux/Mac: Install FFmpeg using the command shown in the prompt

3. **Select Video/Audio Files**
   - Click "Select Video Files"
   - Choose one or more video/audio files (MP4, WEBM, M4A, etc.)
   - Files will appear in the selection list
   - Default folder: `downloads/` (where YouTube videos are saved)

4. **Configure Settings** (Optional)
   - Choose output folder (default: `converted/`)
   - Select audio quality: 128k, 192k, 256k, or 320k
   - Higher quality = larger file size

5. **Convert to MP3**
   - Click "Convert to MP3"
   - Progress bar shows conversion progress
   - Log window displays detailed conversion information
   - Output files saved with same basename as input

6. **Find Your Files**
   - Converted MP3 files are in the `converted/` folder
   - Original video/audio files remain unchanged

## CSV File Format

Your CSV file should contain YouTube links. The downloader supports:
- Plain URLs: `https://www.youtube.com/watch?v=VIDEO_ID`
- Markdown format: `[https://www.youtube.com/watch?v=VIDEO_ID](https://www.youtube.com/watch?v=VIDEO_ID)`

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
├── ffmpeg/                              # FFmpeg portable (Windows, auto-downloaded)
├── scripts/                             # Python scripts
│   ├── youtube_downloader.py           # YouTube downloader application
│   └── video_to_mp3_converter.py       # Video to MP3 converter
├── launchers/                           # Launcher scripts
│   ├── youtube_downloader.bat          # Windows launcher (YouTube)
│   ├── youtube_downloader.sh           # Linux/Mac launcher (YouTube)
│   ├── video_to_mp3_converter.bat      # Windows launcher (Converter)
│   └── video_to_mp3_converter.sh       # Linux/Mac launcher (Converter)
├── requirements.txt                     # Python dependencies
├── .gitignore                           # Git ignore rules
├── AGENT.md                             # Developer/agent documentation
└── README.md                            # This file
```

## Advanced Features

### Auto-loading CSV Files
You can auto-load a CSV file on startup:
- **Windows**: Drag and drop CSV file onto `youtube_downloader.bat`
- **Command line**: Pass CSV file path as first argument to launcher
- The GUI will automatically load the CSV and display the video list

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
- The YouTube downloader uses `yt-dlp` which is actively maintained
- Video to MP3 converter uses FFmpeg for high-quality audio extraction
- Filename patterns sanitize special characters automatically
- Original video files are never modified or deleted during conversion

## For Developers

See `AGENT.md` for detailed development guidelines and project architecture.
