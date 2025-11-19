# AI Album Cover Prompt Template

This template generates album cover prompts for AI cover versions based on Suno sound styles.

## Base Prompt Template

```
SONG_TITLE={{SONG_TITLE}}
ORIGINAL_ARTIST={{ORIGINAL_ARTIST}}
STYLE_DESCRIPTION={{STYLE_DESCRIPTION}}
MOOD_DESCRIPTION={{MOOD_DESCRIPTION}}
VISUAL_TONE={{VISUAL_TONE}}
SUGGESTED_VISUAL_ELEMENTS={{SUGGESTED_VISUAL_ELEMENTS}}
TYPOGRAPHY_STYLE={{TYPOGRAPHY_STYLE}}

Create an album cover image for a cover version of the song "{{SONG_TITLE}}" originally by "{{ORIGINAL_ARTIST}}", in the style of "{{STYLE_DESCRIPTION}}".

The design must visually express the emotion and atmosphere of this musical style — without showing or resembling the original artist or any real person.

Style: {{STYLE_DESCRIPTION}}
Mood: {{MOOD_DESCRIPTION}}
Visual tone: {{VISUAL_TONE}}
Suggested imagery: {{SUGGESTED_VISUAL_ELEMENTS}}
Typography: {{TYPOGRAPHY_STYLE}}
Layout: Vintage vinyl-era cover design, analog look, centered text fitting cleanly into a 2x3 composition window of the 1x1 frame.
Format: square (1:1), high-resolution, suitable for streaming platforms.
Avoid clutter, unrelated visuals, or complex backgrounds that distract from the main layout.
```

## Style-Specific Variations

### 1960s Soul-Blues
- **Visual Tone**: Vintage warm tones, golden lighting, slight film grain, analog depth
- **Suggested Elements**: Retro microphone, soft abstract forms, warm background texture, subtle stage glow
- **Typography**: Classic 1960s serif or script font, centered and readable

### Modern Pop
- **Visual Tone**: Clean, bright, glossy, contemporary
- **Suggested Elements**: Geometric shapes, neon accents, clean lines, modern textures
- **Typography**: Modern sans-serif, bold and readable

### Hip-Hop Trap
- **Visual Tone**: Dark, moody, urban, high contrast
- **Suggested Elements**: Urban textures, neon lights, geometric patterns, street elements
- **Typography**: Bold, angular fonts, urban aesthetic

### R&B Contemporary
- **Visual Tone**: Smooth, sensual, soft lighting, elegant
- **Suggested Elements**: Soft curves, elegant textures, intimate lighting, sophisticated elements
- **Typography**: Elegant serif or modern script, flowing and sensual

### EDM Future Bass
- **Visual Tone**: Bright, euphoric, colorful, energetic
- **Suggested Elements**: Colorful gradients, abstract shapes, energy bursts, futuristic elements
- **Typography**: Modern, bold, dynamic fonts with color accents

### 80s Retro Pop
- **Visual Tone**: Nostalgic, vibrant, neon colors, retro-futuristic
- **Suggested Elements**: Neon lights, synthwave elements, retro patterns, 80s aesthetics
- **Typography**: Retro-futuristic fonts, neon effects, 80s styling

### Classic Rock
- **Visual Tone**: Bold, gritty, powerful, authentic
- **Suggested Elements**: Guitar silhouettes, stage lighting, rock textures, bold graphics
- **Typography**: Bold, impactful fonts, rock aesthetic

### Lo-fi Hip-Hop
- **Visual Tone**: Warm, cozy, nostalgic, soft
- **Suggested Elements**: Soft textures, warm colors, cozy elements, nostalgic items
- **Typography**: Handwritten or soft fonts, cozy aesthetic

### Jazz Big Band
- **Visual Tone**: Classy, sophisticated, golden age, elegant
- **Suggested Elements**: Musical instruments, elegant patterns, sophisticated lighting, classic elements
- **Typography**: Classic serif fonts, elegant and sophisticated

### Ambient Electronic
- **Visual Tone**: Ethereal, atmospheric, soft, meditative
- **Suggested Elements**: Soft gradients, abstract forms, atmospheric textures, minimal elements
- **Typography**: Clean, minimal fonts, ethereal aesthetic

## Usage Instructions

1. **Select Style**: Choose the appropriate style from the Suno sound styles CSV
2. **Fill Variables**: Replace the template variables with specific song information
3. **Customize**: Adjust visual elements and typography based on the specific style
4. **Generate**: Use the completed prompt with your AI image generation tool

## Example Usage

For a 1960s Soul-Blues cover of "Shape of You" by Ed Sheeran:

```
SONG_TITLE=1960s Soul-Blues AI Cover - Ed Sheeran: "Shape of You"
ORIGINAL_ARTIST=Ed Sheeran
STYLE_DESCRIPTION=Soul blues combining emotional delivery with powerful vocals and gospel influence. Heartfelt and powerful.
MOOD_DESCRIPTION=Warm, passionate, and deeply soulful with a nostalgic 1960s vibe
VISUAL_TONE=Vintage warm tones, golden lighting, slight film grain, and analog depth
SUGGESTED_VISUAL_ELEMENTS=Retro microphone, soft abstract forms, warm background texture, subtle stage glow
TYPOGRAPHY_STYLE=Classic 1960s serif or script font, centered and readable, balanced within a 2x3 frame area

Create an album cover image for a cover version of the song "1960s Soul-Blues AI Cover - Ed Sheeran: Shape of You" originally by "Ed Sheeran", in the style of "Soul blues combining emotional delivery with powerful vocals and gospel influence. Heartfelt and powerful.".

The design must visually express the emotion and atmosphere of this musical style — without showing or resembling the original artist or any real person.

Style: Soul blues combining emotional delivery with powerful vocals and gospel influence. Heartfelt and powerful.
Mood: Warm, passionate, and deeply soulful with a nostalgic 1960s vibe
Visual tone: Vintage warm tones, golden lighting, slight film grain, and analog depth
Suggested imagery: Retro microphone, soft abstract forms, warm background texture, subtle stage glow
Typography: Classic 1960s serif or script font, centered and readable, balanced within a 2x3 frame area
Layout: Vintage 1960–1970 vinyl-era cover design, analog look, centered text fitting cleanly into a 2x3 composition window of the 1x1 frame.
Format: square (1:1), high-resolution, suitable for streaming platforms.
Avoid clutter, unrelated visuals, or complex backgrounds that distract from the main layout.
```

## Notes

- Always avoid showing or resembling the original artist or any real person
- Focus on the musical style and mood rather than specific individuals
- Use abstract or symbolic elements that represent the genre
- Maintain high resolution and square format for streaming platforms
- Keep the design clean and focused on the main layout

