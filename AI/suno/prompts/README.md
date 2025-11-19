# Prompt Templates

This folder contains prompt templates for AI functions.

## Available Templates

- `merge_styles.txt` - Template for merging multiple music styles into a cohesive description
- `ai_cover_name.txt` - Template for generating AI cover names
- `album_cover.txt` - Template for generating album cover prompts
- `video_loop.txt` - Template for generating video loop prompts
- `youtube_hashtags.txt` - Template for generating optimized YouTube hashtags

## Adding New Templates

1. Create a new `.txt` file in this directory
2. Name it with the template identifier (e.g., `my_template.txt`)
3. Use `{VARIABLE_NAME}` for single braces variables
4. Use `{{VARIABLE_NAME}}` for double braces variables
5. Call `get_prompt_template('my_template')` in your code

## Variable Substitution

Templates support variable substitution:
- Single braces: `{STYLES_TO_MERGE}` - replaced using `.replace()`
- Double braces: `{{SONG_TITLE}}` - replaced using `.replace()`

Currently, both types use the same replacement method in the code.

