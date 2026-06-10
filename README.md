# WP Plugin Review Assistant

A professional **Windows desktop application** for reviewing WordPress and WooCommerce plugins locally.

## Stack: Python + PySide6

| Choice | Why |
|--------|-----|
| **Python + PySide6** (selected) | Native subprocess support for WP-CLI/PHP, reliable filesystem scanning, smaller install than Electron, strong Windows desktop UX |
| Electron + Node.js (not used) | Heavier runtime; subprocess/file tooling less ergonomic for LocalWP CLI workflows |

No paid AI APIs are required. The app uses **Ollama**, **LM Studio**, or a **rule-based fallback**.

## Features

- **Plugin selection**: folder or ZIP (safe extraction, path traversal rejection)
- **Metadata detection**: name, version, text domain, PHP/WP requirements, WooCommerce usage
- **LocalWP auto-detection**: `C:\Users\<user>\Local Sites\*\app\public`
- **WP-CLI integration**: LocalWP-aware PHP/php.ini detection, site validation, plugin-check install/activate
- **WordPress Plugin Check**: strict JSON findings from `wp plugin check`
- **AGENTS.md static rules**: security, defensive coding, WooCommerce, release readiness
- **17-category checklist**: automated results plus explicit manual/runtime verification states
- **Free local AI summary**: Ollama / LM Studio (optional)
- **Reports**: HTML, JSON, Codex fix prompts

## Requirements

- Windows 10 or later
- Python 3.9 or later
- LocalWP installed (for site integration)
- WP-CLI available on system PATH
- PHP binary (typically available via LocalWP)

## Installation

### 1. Clone or Download

Download the repository and extract to your desired location.

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If you're on Windows and don't have `pip`, follow Python's installation instructions to ensure pip is available.

### 3. Verify Dependencies

Ensure the following are installed and accessible:
- WP-CLI: Run `wp --info` in PowerShell to verify
- LocalWP: Should be installed in `C:\Users\<username>\Local Sites\`
- PHP: Usually available through LocalWP

## Usage

### Starting the Application

```powershell
pip install -r requirements.txt
python main.py
```

Or double-click `run.bat`.

The application window will open. Use **Settings** to configure Ollama/LM Studio (optional).

### Workflow

1. **Plugin Selection**
   - Browse for a WordPress plugin directory or ZIP file
   - Click "Load Plugin" to detect plugin metadata
   - Review detected metadata (name, version, requirements)

2. **Site Configuration**
   - Select a LocalWP site from the dropdown, or manually browse
   - Click "Validate Site" to confirm WordPress installation
   - Verify site information is correct

3. **Run Review**
   - Click "Start Review"
   - Monitor progress as analysis runs
   - Review output messages for any warnings

4. **View Results**
   - Results display as a summary and detailed issue list
   - Issues are organized by severity (Critical, High, Medium, Low, Info)
   - Issues are categorized (Security, WP Standards, WooCommerce, etc.)

5. **Export Results**
   - **HTML Report**: Professional formatted report with styling
   - **JSON Export**: Machine-readable format for tool integration
   - **Codex Prompt**: Copy a structured prompt for fixing issues with Codex

## How It Works

### Plugin Detection
- Reads WordPress plugin header from main PHP file
- Parses `readme.txt` for additional metadata
- Validates plugin structure
- Handles ZIP file extraction safely

### Static Code Analysis
- Regex-based pattern matching for common issues
- Scans PHP files for security vulnerabilities
- Checks WordPress standards compliance
- Detects WooCommerce integration patterns
- Identifies performance risks

### WordPress Plugin Check
- Verifies Plugin Check plugin is installed in target site
- Automatically installs if missing
- Verifies activation after install/activate
- Runs comprehensive checks via WP-CLI using the selected LocalWP site's runtime
- Waits for WP-CLI commands to finish instead of applying fixed command time limits
- Stops with an actionable error instead of generating a clean report when WP-CLI or Plugin Check fails
- Parses and categorizes results

### Report Generation
- Aggregates issues from all sources
- Organizes by severity and category
- Generates professional HTML with styling
- Creates structured Codex fix prompts

## Troubleshooting

### WP-CLI Not Found
- Ensure `wp` is on your system PATH
- Try running `wp --info` from PowerShell
- If using LocalWP, PHP binary should auto-detect

### LocalWP Sites Not Found
- Verify LocalWP sites are in `C:\Users\<username>\Local Sites\`
- Check that WordPress is running in LocalWP
- Try manual path selection

### Plugin Check Installation Fails
- Ensure target WordPress site is running in LocalWP
- Verify internet connection (Plugin Check needs to download from wp.org)
- Try manually running: `wp plugin install plugin-check --activate`

### Slow Analysis
- Large plugins may take time for static analysis
- Consider excluding large dependency folders
- Check system resources (CPU, memory)

## Architecture

```
WP Plugin Review Assistant
├── src/
│   ├── models.py              # Data models
│   ├── utils.py               # Utilities and helpers
│   ├── report_generator.py    # Report generation
│   ├── core/
│   │   ├── plugin_detector.py      # Plugin metadata extraction
│   │   ├── localwp_validator.py    # LocalWP site detection
│   │   ├── wp_cli_runner.py        # WP-CLI integration
│   │   └── plugin_check_runner.py  # Plugin Check integration
│   ├── analysis/
│   │   └── static_analyzer.py      # Static code analysis
│   └── ui/
│       └── main_window.py          # PySide6 UI
├── main.py                         # Entry point
├── requirements.txt                # Python dependencies
└── README.md                       # Documentation
```

## Development

### Running in Debug Mode

The application logs to `wp_plugin_review.log` for debugging:

```bash
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
python main.py
```

### Adding Custom Analysis Rules

Edit `src/analysis/agents_rules_analyzer.py` to add new pattern checks:

```python
NEW_PATTERNS = {
    'pattern_name': {
        'pattern': r'regex_pattern',
        'severity': IssueSeverity.MEDIUM,
        'message': 'Description of issue',
    },
}
```

## Building a Standalone Executable

### With PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "WP-Plugin-Review-Assistant" --add-data "src:src" main.py
```

This creates `dist\WP-Plugin-Review-Assistant.exe`.

## Future Enhancements

- [ ] Custom analysis rule builder
- [ ] Batch plugin review
- [ ] CI/CD integration
- [ ] Plugin comparison tool
- [ ] Performance profiling

## License

GPL v2 or later (WordPress compatibility)

## Support

For issues, questions, or contributions, check the documentation or review the code comments.
