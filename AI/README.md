# AI Directory

This directory contains AI agent prompts and examples for automated music data collection and CSV generation.

## Files

### `sample_prompt.md`
A comprehensive prompt template for AI agents to process user requests for music lists and generate CSV files with YouTube search URLs. This prompt includes:

- Clear instructions for data gathering
- URL encoding guidelines
- CSV formatting requirements
- Example variations for different data types (songs, albums, artists)
- Error handling guidelines

### `example_output.csv`
A sample CSV file demonstrating the expected output format with:
- Proper CSV formatting with quoted fields
- YouTube search URLs for each entry
- Consistent data structure
- Real-world examples from popular music

## Usage

1. Use the `sample_prompt.md` as a template for creating AI agent prompts
2. Customize the prompt based on specific requirements (different data fields, search criteria, etc.)
3. Use the `example_output.csv` as a reference for expected output format
4. Ensure all YouTube URLs are search URLs (not direct video links)

## Key Features

- **Search URLs**: All video links point to YouTube search results, not specific videos
- **URL Encoding**: Proper encoding of special characters and spaces
- **Consistent Format**: Standardized CSV structure with quoted fields
- **Flexible**: Adaptable for different types of music data requests

## Integration

This AI directory is designed to work with the existing audio tools in the parent directory, providing a foundation for automated music data collection and processing workflows.
