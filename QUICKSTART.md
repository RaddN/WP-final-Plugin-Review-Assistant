# Quick Start Guide

## Installation (First Time)

1. **Download & Extract**
   - Extract the WP Plugin Review Assistant folder to your desired location
   - Remember the folder path (e.g., `C:\Users\YourName\Desktop\WP-Plugin-Review-Assistant`)

2. **Install Python (if not already installed)**
   - Download Python 3.9+ from https://www.python.org
   - During installation, **check "Add Python to PATH"**

3. **Verify WP-CLI**
   - Open PowerShell
   - Run: `wp --info`
   - If not found, ensure WP-CLI is installed: https://wp-cli.org/#installing

4. **Install Dependencies**
   - Open PowerShell in the WP Plugin Review Assistant folder
   - Run: `pip install -r requirements.txt`
   - Wait for installation to complete

## Running the Application

### Method 1: Quick Start (Easiest)
- Double-click `run.bat` in the folder
- The application will start (dependencies auto-install if needed)

### Method 2: From PowerShell
```powershell
cd "C:\path\to\WP-Plugin-Review-Assistant"
python main.py
```

### Method 3: Standalone Executable (After Build)
- Run `build.ps1` in PowerShell to create a standalone .exe
- Find the .exe in the `dist` folder
- Double-click to run without Python required

## Common Issues

### "Python not found"
- Ensure Python is in PATH: `python --version`
- Reinstall Python and check "Add to PATH" during installation

### "wp command not found"
- Verify WP-CLI: `wp --info`
- Ensure it's in PATH or accessible from system
- LocalWP includes WP-CLI; ensure LocalWP is installed

### "Module not found" errors
- Run: `pip install -r requirements.txt` again
- Ensure you're using Python 3.9+: `python --version`

### Slow performance
- First run may be slow as dependencies load
- Large plugins take time for static analysis
- Consider running analysis in background

## Typical Workflow

1. **Open WP Plugin Review Assistant**
   - Run `run.bat` or `python main.py`

2. **Load Plugin**
   - Go to "Plugin Selection" tab
   - Click "Browse" and select plugin folder
   - Click "Load Plugin"

3. **Select Site**
   - Go to "Site Configuration" tab
   - Select LocalWP site from dropdown or browse manually
   - Click "Validate Site"

4. **Run Review**
   - Go to "Review" tab
   - Ensure checks are enabled (Plugin Check and Static Analysis)
   - Click "Start Review"
   - Wait for analysis to complete

5. **Review Results**
   - Go to "Results" tab
   - View summary and issue list
   - Click "Export HTML Report" to generate professional report
   - Click "Copy Codex Prompt" to copy fix suggestions to Claude Code

## Tips

- **First time slow**: Plugin Check plugin installation takes time
- **ZIP files**: Automatically extracted to temp folder during analysis
- **Reports**: HTML reports are fully self-contained and can be shared
- **Codex prompts**: Ready to paste into Claude Code for automated fixes

## Support

- Check `README.md` for detailed documentation
- Review logs in `wp_plugin_review.log` for debugging
- Ensure LocalWP site is running before analysis

## Next Steps

- Review discovered issues in the Results tab
- Export HTML report for sharing with team
- Use Codex prompt in Claude Code to fix identified issues
- Re-run review after fixes to verify improvements
