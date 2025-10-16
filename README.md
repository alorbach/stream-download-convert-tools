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

## Requirements

- Python 3.7 or higher
- Internet connection for downloading

## Installation & Usage

### Windows

1. **Basic Launch**: Double-click `launchers/youtube_downloader.bat`
   - First run will automatically create virtual environment and install dependencies
   - Subsequent runs will launch directly

2. **Auto-load CSV**: Drag and drop a CSV file onto the launcher, or:
   ```cmd
   launchers\youtube_downloader.bat input\top100.csv
   ```

### Linux/Mac

1. Make the launcher executable (first time only):
   ```bash
   chmod +x launchers/youtube_downloader.sh
   ```

2. **Basic Launch**:
   ```bash
   ./launchers/youtube_downloader.sh
   ```

3. **Auto-load CSV**:
   ```bash
   ./launchers/youtube_downloader.sh input/top100.csv
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
├── venv/                           # Virtual environment (auto-created)
├── input/                          # Input CSV files
│   └── top100.csv                 # Sample YouTube links
├── downloads/                      # Downloaded videos (auto-created)
├── scripts/                        # Python scripts
│   └── youtube_downloader.py      # Main downloader application
├── launchers/                      # Launcher scripts
│   ├── youtube_downloader.bat     # Windows launcher
│   └── youtube_downloader.sh      # Linux/Mac launcher
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
├── AGENT.md                        # Developer/agent documentation
└── README.md                       # This file
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

### GUI Not Showing
Ensure tkinter is installed with Python:
- Windows: Included by default
- Linux: Install with `sudo apt-get install python3-tk`
- Mac: Included by default

## Notes

- All launchers automatically manage virtual environments
- Downloaded files are saved to `downloads/` folder by default
- The tool uses `yt-dlp` which is actively maintained
- Filename patterns sanitize special characters automatically

## For Developers

See `AGENT.md` for detailed development guidelines and project architecture.
