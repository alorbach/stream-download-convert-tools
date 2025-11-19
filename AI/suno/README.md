# Suno Sound Styles

This folder contains curated Suno sound styles in CSV and a small GUI to browse and copy prompts to the clipboard.

- `suno_sound_styles.csv`: curated styles and prompts
- Use launcher scripts to run the GUI: see `launchers/`.

## Azure AI Configuration

The application supports three Azure AI profiles for different purposes:

1. **Text** - For text generation (style merging, AI cover names)
2. **Image Gen** - For image generation (album cover prompts)
3. **Video Gen** - For video generation (video loop prompts)

Each profile can have its own endpoint, model, deployment, subscription key, and API version.
Configure these in the Settings dialog (Menu → Settings).