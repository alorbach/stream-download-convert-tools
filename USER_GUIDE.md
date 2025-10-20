# Audio Tools - Complete User Guide

Welcome to Audio Tools! This comprehensive guide will help you get the most out of your audio and video processing workflow.

## Table of Contents

1. [Getting Started](#getting-started)
2. [YouTube Downloader](#youtube-downloader)
3. [Video to MP3 Converter](#video-to-mp3-converter)
4. [Audio Modifier](#audio-modifier)
5. [Settings Configuration](#settings-configuration)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Features](#advanced-features)
8. [Legal and Compliance](#legal-and-compliance)

## Getting Started

### First Launch

When you first launch Audio Tools, you'll see a legal disclaimer. Please read it carefully and click "I Accept" to continue. This ensures you understand your responsibilities when using the software.

### System Requirements

- **Python 3.7 or higher**
- **Internet connection** (for YouTube downloads)
- **FFmpeg** (automatically downloaded on Windows)
- **Sufficient disk space** (depends on your downloads)

### Launching the Application

**Windows:**
- Double-click `launchers/audio_tools_unified.bat`
- First run will create a virtual environment and install dependencies

**Linux/Mac:**
- Make executable: `chmod +x launchers/audio_tools_unified.sh`
- Run: `./launchers/audio_tools_unified.sh`

### Auto-loading CSV Files

You can automatically load a CSV file on startup:

**Windows:**
- Drag and drop a CSV file onto `audio_tools_unified.bat`
- Or use command line: `launchers\audio_tools_unified.bat input\top100.csv`

**Linux/Mac:**
- Command line: `./launchers/audio_tools_unified.sh input/top100.csv`

## YouTube Downloader

### Step 1: Prepare Your CSV File

Your CSV file should contain YouTube links. Supported formats:

**Direct YouTube URLs:**
```csv
Rank,Song Title,Artist,Year,Video Link
1,Despacito,Luis Fonsi ft. Daddy Yankee,2017,https://www.youtube.com/watch?v=kJQP7kiw5Fk
```

**Markdown Format:**
```csv
Rank,Song Title,Artist,Year,Video Link
1,Despacito,Luis Fonsi ft. Daddy Yankee,2017,[https://www.youtube.com/watch?v=kJQP7kiw5Fk](https://www.youtube.com/watch?v=kJQP7kiw5Fk)
```

**YouTube Search URLs:**
```csv
Rank,Song Title,Artist,Year,Video Link
1,Bridge Over Troubled Water,Simon & Garfunkel,1970,https://www.youtube.com/results?search_query=Simon+%26+Garfunkel+-+Bridge+Over+Troubled+Water
```

### Step 2: Load Your CSV File

1. Click "Select CSV File" in the YouTube Downloader tab
2. Choose your CSV file
3. Preview will show the file contents
4. The video list will populate automatically

### Step 3: Select a Video

1. Click on a video in the list
2. Click "Fetch Available Streams"
3. Wait for the stream information to load

### Step 4: Choose Your Stream

Streams are organized by type:

**Video + Audio (Recommended):**
- Complete files ready to play
- Best quality options
- Larger file sizes

**Video Only:**
- Video without audio track
- Useful for video editing
- Requires separate audio download

**Audio Only:**
- Audio files (MP3, M4A, etc.)
- Smaller file sizes
- Perfect for music

### Step 5: Download

**Single Download:**
1. Select your preferred stream
2. Click "Download Selected Stream"
3. Watch the progress bar and log output

**Batch Downloads:**
1. Select multiple videos (Ctrl+Click)
2. Choose "Download Selected Videos" or "Download All Videos"
3. All videos will use the same format

### Download Tips

- **Quality vs Size**: Higher quality = larger files
- **Format Selection**: MP4 is most compatible, WEBM is more efficient
- **Network**: Stable internet connection recommended
- **Storage**: Check available disk space before large downloads

## Video to MP3 Converter

### Step 1: Select Video Files

1. Click "Select Video Files" in the Video to MP3 tab
2. Choose one or more video files
3. Supported formats: MP4, WEBM, M4A, AVI, MOV, MKV, FLV, WMV
4. Default folder: `downloads/` (where YouTube videos are saved)

### Step 2: Configure Settings

**Output Folder:**
- Default: `converted/`
- Click "Browse" to change location

**Audio Quality:**
- **128k**: Smallest files, basic quality
- **192k**: Good balance (recommended)
- **256k**: High quality
- **320k**: Maximum quality, largest files

### Step 3: Convert

1. Click "Convert to MP3"
2. Watch the progress bar
3. Monitor the log for detailed information
4. Files are saved with the same basename as input

### Conversion Tips

- **Batch Processing**: Select multiple files for efficiency
- **Quality Settings**: 192k is usually sufficient for most uses
- **File Organization**: Use descriptive folder names
- **Backup**: Original files are never modified

## Audio Modifier

### Step 1: Select Audio Files

1. Click "Select Audio Files" in the Audio Modifier tab
2. Choose audio files: MP3, M4A, WAV, OGG, FLAC
3. Default folder: `converted/` (where MP3 files are saved)

### Step 2: Configure Modifications

**Speed Adjustment:**
- Range: -50% to +100%
- Negative values slow down audio
- Positive values speed up audio
- Changes tempo without affecting pitch

**Pitch Adjustment:**
- Range: -12 to +12 semitones
- Negative values lower pitch
- Positive values raise pitch
- 12 semitones = 1 octave
- Changes pitch without affecting tempo

**Audio Quality:**
- Same options as converter: 128k, 192k, 256k, 320k

### Step 3: Use Quick Presets

**Common Presets:**
- **Slower -10%**: Reduce speed by 10%
- **Faster +10%**: Increase speed by 10%
- **Pitch -1**: Lower pitch by 1 semitone
- **Pitch +1**: Raise pitch by 1 semitone
- **Reset**: Set both to 0 (no change)

### Step 4: Modify Audio

1. Click "Modify Audio Files"
2. Watch the progress bar
3. Monitor the log for processing details
4. Output files are saved with descriptive suffixes

### Modification Tips

- **Combined Effects**: You can adjust both speed and pitch
- **Quality Preservation**: Higher quality settings preserve audio fidelity
- **Testing**: Try small adjustments first
- **Backup**: Original files are never modified

## Settings Configuration

### Download Settings

**Download Folder:**
- Default: `downloads/`
- Click "Browse" to change location
- Ensure sufficient disk space

**Filename Pattern:**
Customize how downloaded files are named using CSV fields:

**Available Fields:**
- `{Rank}` - Rank number
- `{Song Title}` - Song title
- `{Artist}` - Artist name
- `{Year}` - Year
- `{Views (Billions)}` - View count

**Default Pattern:** `{Rank}_{Song Title}_{Artist}`

**Examples:**
- `{Artist} - {Song Title} ({Year})`
- `{Rank:02d} - {Song Title}`
- `{Year} - {Artist} - {Song Title}`

### Converter Settings

**Output Folder:**
- Default: `converted/`
- Change location as needed

**Audio Quality:**
- Set default quality for conversions
- Can be overridden per conversion

### Modifier Settings

**Output Folder:**
- Default: `converted_changed/`
- Change location as needed

**Audio Quality:**
- Set default quality for modifications
- Can be overridden per modification

## Troubleshooting

### Common Issues

**Virtual Environment Problems:**
1. Delete the `venv/` folder
2. Re-run the launcher script
3. Let it recreate the environment

**Download Failures:**
1. Check internet connection
2. Verify YouTube URL is valid
3. Some videos may be geo-restricted
4. Update yt-dlp: launcher auto-updates dependencies

**Conversion Failures:**
1. Ensure FFmpeg is installed
2. Check video files are not corrupted
3. Try different audio quality setting
4. Verify sufficient disk space

**GUI Not Showing:**
- **Windows**: Included by default
- **Linux**: Install with `sudo apt-get install python3-tk`
- **Mac**: Included by default

**FFmpeg Not Found:**
- **Windows**: App will offer to download automatically
- **Linux**: Install with `sudo apt-get install ffmpeg`
- **Mac**: Install with `brew install ffmpeg`

### Error Messages

**"Invalid YouTube URL":**
- Check URL format
- Ensure it's a valid YouTube link
- Try copying the URL again

**"File not found":**
- Check file path
- Ensure file exists
- Verify file permissions

**"Insufficient disk space":**
- Free up disk space
- Choose different output folder
- Reduce quality settings

**"Network error":**
- Check internet connection
- Try again later
- Check firewall settings

## Advanced Features

### Batch Operations

**Batch Downloads:**
- Select multiple videos
- Choose consistent format
- Monitor progress in log

**Batch Conversions:**
- Select multiple video files
- Convert all at once
- Maintain quality settings

**Batch Modifications:**
- Select multiple audio files
- Apply same modifications
- Process efficiently

### File Management

**Folder Organization:**
- Use descriptive folder names
- Organize by date, artist, or genre
- Keep original files separate

**Filename Patterns:**
- Create consistent naming
- Include metadata
- Use date stamps

### Quality Optimization

**Download Quality:**
- Balance quality vs file size
- Consider storage space
- Test different formats

**Conversion Quality:**
- 192k is usually sufficient
- Higher quality for archiving
- Lower quality for mobile devices

**Modification Quality:**
- Higher quality preserves fidelity
- Lower quality reduces file size
- Test different settings

## Legal and Compliance

### Important Legal Notice

This software is provided for educational and personal use only. Users are responsible for:

- Complying with applicable copyright laws in their jurisdiction
- Respecting YouTube's Terms of Service
- Only downloading content they have legal rights to access
- Understanding fair use guidelines for their intended use

### Fair Use Guidelines

**Educational Use:**
- Classroom instruction
- Research purposes
- Academic projects

**Personal Use:**
- Personal backup copies
- Accessibility modifications
- Format conversion for personal devices

**Commercial Use:**
- May require additional permissions
- Check with content owners
- Consider licensing agreements

### Best Practices

**Respect Copyright:**
- Only download content you have rights to
- Don't redistribute without permission
- Credit original creators

**Follow Platform Rules:**
- Respect YouTube's Terms of Service
- Don't circumvent access controls
- Use responsibly

**Legal Compliance:**
- Understand local laws
- Seek legal advice if unsure
- Use common sense

### Resources

**YouTube Terms of Service:**
https://www.youtube.com/static?template=terms

**Fair Use Guidelines (US):**
https://www.copyright.gov/fair-use/

**Copyright Information:**
https://www.copyright.gov/

## Support and Updates

### Getting Help

1. Check this user guide first
2. Review troubleshooting section
3. Check for software updates
4. Contact support if needed

### Software Updates

- Launcher automatically updates dependencies
- Check for new versions regularly
- Backup your settings and files

### Feedback

We welcome your feedback! Please let us know:
- What features you'd like to see
- Any bugs or issues you encounter
- Suggestions for improvement

---

**Remember**: Always use this software responsibly and in compliance with applicable laws and terms of service. The authors disclaim any responsibility for misuse of this software.

Happy audio processing! 🎵
