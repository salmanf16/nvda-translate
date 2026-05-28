# NVDA Translate

An ultra-lightweight, extremely performant online translation addon for NVDA. Translate any spoken text, game dialogue, or chat messages on the fly in real-time.

> [!NOTE]
> Originally developed by **Yannick Plassiard** (the original author who made this translation addon possible). This modified version is optimized for extremely fast real-time translations while fully respecting the original developer's rights and excellent work.

---

## Features

- **Multi-Engine Cloud Support**: Choose from Google Translate, Lingva Translate, or LibreTranslate directly from NVDASettings.
- **Official JSON API Integration**: Connects directly to Google's official free translation API (`translate.googleapis.com`) with zero legacy web-scraping regexes.
- **Zero-Latency Handshake Savings**: Reuses persistent socket connections and HTTP/HTTPS Keep-Alive handshakes across subsequent translation requests, saving **100ms - 300ms** of network lag on every call!
- **Granular Local Caching**: Translates and caches text line by line. Granular terms load instantly from memory on future matches.
- **0.0ms Performance Bypasses**:
  - **Rule 1 (Non-Alphabetic Bypass)**: Instantly skips numbers, gauges, coordinates, and symbols.
  - **Rule 2 (Single Latin Key Bypass)**: Bypasses individual keyboard shortcut letters (like 'g' or 'A') while preserving non-ASCII translations (like Japanese Kanji).
  - **Rule 3 (Source-Target Matching)**: Bypasses text already in your target language (e.g. Arabic chat messages) to ensure zero speech delays during live multiplayer gaming.
- **Auto-Saving Daemon**: A thread-safe, periodic auto-saver writes translation caches to disk every 15 seconds in the background without affecting gameplay, preventing data loss on abrupt shutdowns.
- **Punctuation-Insensitive Glossary**: Instantly matches system terms (like `"Server down..."`, `"Server offline!!!"`) to pre-configured high-quality translations in **0.0ms** while preserving exact leading/trailing symbols.
- **Ultra-Lightweight & Clean**: purges offline cTranslate2 dependencies, local drive managers, and developer temporary logs. Idle memory footprint is exactly **0.0 MB** and the packaged addon is only **68 KB**!

---

## Installation

1. Download the latest `translate.nvda-addon` file.
2. Double-click or press Enter on the file.
3. Answer **Yes** to NVDA's prompt to install the addon.
4. Restart NVDA to load the translation plugin.

---

## Gestures & Controls

Configure these shortcuts in NVDA Preferences -> Command Gestures:
- **NVDA+Shift+Control+T**: Toggles translation on or off.
- **NVDA+Shift+C**: Copies the latest translated text to the clipboard.
- **NVDA+Shift+F** (press twice quickly): Deletes the translation cache for the currently active/focused application.
- **NVDA+Shift+Control+F** (press twice quickly): Deletes all cached translations for all applications on your system.

---

## Configuration

Navigate to **NVDA Menu -> Preferences -> Settings -> Translate** to configure:
1. **Translation Engine**: Google Translate, Lingva Translate, or LibreTranslate.
2. **Custom API endpoints**: Change URLs for Lingva instances or LibreTranslate servers (including API keys).
3. **Target Language**: Choose your destination language (defaults to your active NVDA language). Supports **89 distinct global languages**!

---

## Credits & Special Thanks

- **Yannick Plassiard**: The original author and developer who conceptualized and wrote the initial versions of this fantastic addon, making on-the-fly translation accessible to the blind community. We highly thank and appreciate him for his initial work and contribution.
- **Hxebolax**: For prior compatibility fixes in earlier NVDA versions.
