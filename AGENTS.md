# Agent Instructions for stream-download-convert-tools Project

## Project Overview
This repository contains Python-based audio/video tools for downloading and processing YouTube content. The main application is now a unified tool with tabbed interface, though individual tools remain available for legacy users.

## Important Guidelines

### Python Environment Management
- **ALL Python scripts in this project use virtual environments (venv) automatically**
- Scripts are launched via launcher scripts that handle venv setup and activation
- Never run Python scripts directly - always use the provided launchers
- Virtual environment is located in `venv/` directory (gitignored)

### Script Architecture
1. **Launcher Scripts** (`.bat` for Windows, `.sh` for Linux/Mac)
   - Check if venv exists, create if needed
   - Activate venv
   - Install/update requirements
   - Launch the main Python script

2. **Python Scripts** (`.py`)
   - Assume venv is already activated
   - Use standard Python imports
   - Include GUI support where applicable (tkinter)

### Dependencies
- Core dependencies listed in `requirements.txt`
- Uses `yt-dlp` for YouTube downloading (modern fork of youtube-dl)
- Uses `FFmpeg` for video/audio conversion and modification
- GUI built with tkinter (included in Python standard library)

### Project Structure
```
stream-download-convert-tools/
├── venv/                    # Virtual environment (auto-created, gitignored)
├── input/                   # Input CSV files
│   └── top100.csv          # Sample YouTube links CSV
├── downloads/              # Downloaded files go here (gitignored)
├── converted/              # Converted MP3 files (gitignored)
├── converted_changed/      # Modified audio files (gitignored)
├── ffmpeg/                 # FFmpeg portable installation (gitignored)
├── scripts/                # Python application scripts
│   ├── stream_download_convert_tools_unified.py      # Unified application (RECOMMENDED)
│   ├── youtube_downloader.py      # Individual YouTube downloader
│   ├── video_to_mp3_converter.py   # Individual Video to MP3 converter
│   └── audio_modifier.py           # Individual Audio modifier
├── launchers/              # Launcher scripts
│   ├── stream_download_convert_tools_unified.bat     # Windows launcher (Unified - RECOMMENDED)
│   ├── stream_download_convert_tools_unified.sh      # Linux/Mac launcher (Unified - RECOMMENDED)
│   ├── youtube_downloader.bat     # Windows launcher (Individual)
│   ├── youtube_downloader.sh       # Linux/Mac launcher (Individual)
│   ├── video_to_mp3_converter.bat # Windows launcher (Individual)
│   ├── video_to_mp3_converter.sh  # Linux/Mac launcher (Individual)
│   ├── audio_modifier.bat          # Windows launcher (Individual)
│   └── audio_modifier.sh           # Linux/Mac launcher (Individual)
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore rules
├── AGENT.md               # This file
└── README.md              # User documentation
```

### CSV File Format
The project uses CSV files with YouTube links. Example format from `input/top100.csv`:
- Column 1: Rank (numeric rank)
- Column 2: Song Title (song name)
- Column 3: Artist (artist name)
- Column 4: Views (Billions) (view count)
- Column 5: Year (release year)
- Column 6: Video Link (YouTube link in markdown format)

**Note**: Links are in markdown format `[URL](URL)` - extract the actual URL when parsing.

### User Preferences
- Merge settings with minimal comments [[memory:8445651]]
- Maintain ASCII-only style in outputs, avoid non-ASCII characters [[memory:8445636]]
- Do not delete files - user does their own testing [[memory:8445615]]

### Development Guidelines
1. Always create launcher scripts for new Python tools
2. Test scripts assume venv is working
3. Keep GUI simple and intuitive
4. Provide clear error messages
5. Log operations for debugging

### Common Tasks

#### Adding a New Script
1. Create Python script in `scripts/` directory
2. Add any new dependencies to `requirements.txt`
3. Create launcher in `launchers/` directory
4. Update README.md with usage instructions
5. Test launcher on target platform

#### Working with Unified Application
- **Primary Application**: `stream_download_convert_tools_unified.py` - Contains all three tools in tabbed interface
- **Launcher**: `stream_download_convert_tools_unified.bat/.sh` - Main launcher for unified application
- **Individual Tools**: Still available for users who prefer separate applications
- **Development**: When modifying functionality, update both unified and individual tools if needed

#### Updating Dependencies
1. Modify `requirements.txt`
2. Run launcher - it will auto-update packages
3. Or manually: `venv\Scripts\pip install -r requirements.txt`

#### Troubleshooting
- If venv is corrupted: Delete `venv/` folder and re-run launcher
- If yt-dlp fails: May need to update it (`pip install -U yt-dlp`)
- If GUI doesn't show: Check tkinter is available in Python installation

### External Tools Used
- **yt-dlp**: YouTube downloading (https://github.com/yt-dlp/yt-dlp)
- **FFmpeg**: Video/audio conversion and modification (https://ffmpeg.org/)
  - Windows: Automatically downloaded by video_to_mp3_converter.py and audio_modifier.py
  - Linux/Mac: User must install manually
- **tkinter**: GUI framework (included with Python)
- **csv**: CSV parsing (Python standard library)

## Notes for AI Agents
- When user requests new scripts, follow the established patterns
- Always create both the Python script and its launcher
- Update this AGENT.md if project structure changes significantly
- Respect user preferences about file deletion and ASCII-only output

## Agent Workflows

### FINISH Workflow
When closing out work on a task or feature:

1. **Reconcile Tasks**
   - Mark completed todo items as done
   - Cancel obsolete tasks
   - Document any blockers or follow-ups

2. **Run Validation**
   - Test launcher scripts on target platform
   - Verify Python scripts run without errors
   - Check for linter errors in modified files
   - Test GUI functionality if applicable
   - Verify venv creation and dependency installation

3. **Fix Issues**
   - Address any errors or warnings found
   - Re-run validation until clean

4. **Update Documentation**
   - Update README.md if user-facing changes were made
   - Update AGENT.md if project structure or patterns changed
   - Add changelog entries if CHANGELOG.md exists

5. **Summarize**
   - List what changed
   - Note what was verified
   - Document any known limitations

### SUMMARIZE Workflow
Generate two COPY-READY summaries for Git workflow:

1. **Pull Request Summary** (for reviewers):
   - What changed (high-level bullets)
   - Why it changed (intent and benefits)
   - Validation performed (what was tested)
   - Risks/notes (breaking changes, follow-ups needed)
   - Format as complete markdown ready to paste into PR description

2. **Squashed Commit Message** (concise):
   - Imperative subject line (max 72 chars)
   - Short body explaining what and why (wrapped at 72 chars)
   - Optional bullet list of key changes
   - Format in code block ready to copy/paste directly into Git

**Important**: Both outputs must be complete, properly formatted, and immediately
usable without any editing required

### Shortcut Keywords
Future agents can use these keywords to trigger workflows:

- **FINISH**: Execute close-out flow (reconcile tasks, run validation, update docs, summarize changes)
- **SUMMARIZE**: Produce PR description and squashed commit message summaries

