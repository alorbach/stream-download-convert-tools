# Stream Download Convert Tools - Complete User Guide

Welcome to Stream Download Convert Tools! This comprehensive guide will help you get the most out of your audio and video processing workflow.

![Stream Download Convert Tools - Unified Application](docs/screenshot.png)

## Table of Contents

1. [Getting Started](#getting-started)
2. [YouTube Downloader](#youtube-downloader)
3. [Video to MP3 Converter](#video-to-mp3-converter)
4. [Audio Modifier](#audio-modifier)
5. [Suno Style Browser](#suno-style-browser)
6. [Settings Configuration](#settings-configuration)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)
9. [Legal and Compliance](#legal-and-compliance)

## Getting Started

### First Launch

When you first launch Stream Download Convert Tools, you'll see a legal disclaimer. Please read it carefully and click "I Accept" to continue. This ensures you understand your responsibilities when using the software.

### System Requirements

- **Python 3.7 or higher**
- **Internet connection** (for YouTube downloads)
- **FFmpeg** (automatically downloaded on Windows)
- **Sufficient disk space** (depends on your downloads)

### Launching the Application

**Windows:**
- Double-click `launchers/stream_download_convert_tools_unified.bat`
- First run will create a virtual environment and install dependencies

**Linux/Mac:**
- Make executable: `chmod +x launchers/stream_download_convert_tools_unified.sh`
- Run: `./launchers/stream_download_convert_tools_unified.sh`

### Auto-loading CSV Files

You can automatically load a CSV file on startup:

**Windows:**
- Drag and drop a CSV file onto `stream_download_convert_tools_unified.bat`
- Or use command line: `launchers\stream_download_convert_tools_unified.bat input\top100.csv`

**Linux/Mac:**
- Command line: `./launchers/stream_download_convert_tools_unified.sh input/top100.csv`

## YouTube Downloader

![YouTube Downloader Tab](docs/youtube_downloader.png)

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

![Video to MP3 Converter Tab](docs/video_to_mp3_converter.png)

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

![Audio Modifier Tab](docs/audio_modifier.png)

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

## Suno Style Browser

The Suno Style Browser is a specialized tool for browsing music styles and generating AI-powered content for music covers, including album artwork and video loops.

### Getting Started with Suno Style Browser

**Windows:**
- Double-click `launchers/suno_style_browser.bat`
- First run will create a virtual environment and install dependencies

**Linux/Mac:**
- Make executable: `chmod +x launchers/suno_style_browser.sh`
- Run: `./launchers/suno_style_browser.sh`

**Auto-load CSV:**
- Command line: `launchers\suno_style_browser.bat AI\suno\suno_sound_styles.csv` (Windows)
- Command line: `./launchers/suno_style_browser.sh AI/suno/suno_sound_styles.csv` (Linux/Mac)

### Step 1: Configure Azure AI Settings

Before using AI features, you need to configure Azure AI access:

1. Go to **Settings > Azure AI Settings**
2. Configure three profiles:

**Text Profile (for style merging and prompts):**
- Endpoint: Your Azure OpenAI endpoint
- Model Name: gpt-4
- Deployment: Your GPT-4 deployment name
- Subscription Key: Your Azure API key
- API Version: 2024-12-01-preview

**Image Gen Profile (for album covers):**
- Endpoint: Your Azure OpenAI endpoint
- Model Name: dall-e-3
- Deployment: Your DALL-E 3 deployment name
- Subscription Key: Your Azure API key
- API Version: 2024-02-15-preview

**Video Gen Profile (for video loops):**
- Endpoint: Your Azure OpenAI endpoint
- Model Name: imagevideo (or sora-2)
- Deployment: Your video generation deployment name
- Subscription Key: Your Azure API key
- API Version: 2024-02-15-preview

### Step 2: Browse Music Styles

1. **Load CSV File**: The tool automatically loads `AI/suno/suno_sound_styles.csv` by default
2. **Use Filters**: 
   - **Search**: General search across all fields
   - **Style**: Filter by style name
   - **Artists**: Filter by sample artists
   - **Decade**: Filter by decade range
   - **Tempo**: Filter by tempo (BPM)
3. **Select Style**: Click on a style in the list to view details
4. **View Details**: See style information including mood, tempo, instrumentation, and more

### Step 3: Enter Song Details

1. **AI Cover Name**: Enter or generate a name for your AI cover
2. **Song Name**: Enter the original song name
3. **Artist**: Enter the original artist name
4. **Lyrics**: Paste song lyrics (up to 20,000 characters)
5. **Styles**: Enter one or more style names to use
6. **Merged Style**: Result after merging styles (see Step 4)

### Step 4: Merge Styles

If you want to combine multiple styles:

1. Enter multiple style names in the **Styles** field (comma-separated)
2. Click **Merge Styles**
3. Wait for AI to generate a merged style description
4. The result appears in the **Merged Style** field

### Step 5: Generate AI Cover Name

1. Ensure **Song Name** and **Artist** are filled
2. Ensure **Styles** or **Merged Style** is filled
3. Click **Generate AI Cover Name**
4. The generated name appears in the **AI Cover Name** field

### Step 6: Generate Album Cover

1. **Generate Prompt**: Click **Gen Album Cover Prompt** to create an AI prompt
2. **Review Prompt**: Check the generated prompt in the Album Cover tab
3. **Inject Extra Commands** (Optional): Click **Run Album Cover Prompt** to add extra instructions
4. **Generate Image**: The tool will call Azure DALL-E 3 to generate the image
5. **Preview**: Generated image appears in the preview section
6. **Save**: Choose where to save the PNG file

### Step 7: Generate Video Loop

1. **Generate Prompt**: Click **Gen Video Loop Prompt** (requires album cover prompt first)
2. **Review Prompt**: Check the generated prompt in the Video Loop tab
3. **Configure Options**:
   - **Size**: 720x1280 (portrait) or 1280x720 (landscape)
   - **Seconds**: 4, 8, or 12 seconds
4. **Generate Video**: Click **Run Video Loop Prompt**
5. **Save**: Choose where to save the MP4 file

### Step 8: Export YouTube Description

1. Ensure **Song Name** and **Artist** are filled
2. Click **Export YouTube Description**
3. Choose save location
4. The exported file includes:
   - YouTube title
   - Song details
   - SEO-optimized description
   - Hashtags
   - Credits and disclaimers

### Saving and Loading Song Details

**Save Song Details:**
- Click **Save** (Ctrl+S) to save to config file
- If AI Cover Name is set, you'll be prompted to save to a separate JSON file
- Settings are saved in `scripts/suno_style_browser_config.json`

**Load Song Details:**
- Click **Load** to load from a JSON file
- Restores all song details, styles, lyrics, and prompts

**Clear All:**
- Click **Clear All** to reset all fields

### Keyboard Shortcuts

- **Ctrl+S**: Save song details
- **Ctrl+D**: Toggle debug output
- **Ctrl+F**: Focus search field
- **F5**: Reload CSV file

### Debug Output

The tool includes comprehensive debug logging:
- Click **▼ Debug Output** to show/hide debug panel
- Click **Clear** to clear debug messages
- Debug messages show:
  - API calls and responses
  - Configuration details
  - Error messages
  - Operation status

### Tips for Best Results

**Style Selection:**
- Select a style that matches your song's mood
- Use style merging for unique combinations
- Review style details before generating prompts

**Album Cover Generation:**
- Generate prompt first, then review before generating image
- Use "Inject Extra Commands" to refine the prompt
- Album covers are generated at 1024x1024 resolution

**Video Loop Generation:**
- Generate album cover prompt first for better results
- Choose appropriate size for your platform (portrait for mobile, landscape for desktop)
- Video generation may take several minutes

**YouTube Description:**
- Export after completing all other steps
- Review the generated description before using
- Customize hashtags and links as needed

### Troubleshooting Suno Style Browser

**Azure AI Configuration Errors:**
- Verify all endpoints are correct
- Check subscription keys are valid
- Ensure API versions match your Azure deployment
- Check debug output for detailed error messages

**Style Not Found:**
- Verify CSV file is in correct location
- Check CSV file format matches expected structure
- Use "Reload" button to refresh styles

**Image Generation Fails:**
- Check image_gen profile configuration
- Verify DALL-E 3 deployment is active
- Check API quota and limits
- Review debug output for specific errors

**Video Generation Fails:**
- Check video_gen profile configuration
- Verify video generation deployment is active
- Video generation may take 5+ minutes
- Check debug output for job status

## Settings Configuration

![Settings Tab](docs/settings.png)

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
