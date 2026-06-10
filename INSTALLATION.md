# Installation & Setup Guide

## System Requirements

- **OS**: Windows 10 or Windows 11
- **Python**: 3.9 or later
- **LocalWP**: Installed and configured
- **WP-CLI**: Available on system PATH
- **PHP**: 7.4 or later (usually available via LocalWP)
- **Memory**: Minimum 2GB RAM available
- **Disk Space**: ~500MB for dependencies

## Step-by-Step Installation

### 1. Download & Extract

1. Download or clone the WP Plugin Review Assistant
2. Extract to a convenient location (e.g., `C:\Users\YourName\Desktop\`)
3. Note the full path to the folder

### 2. Install Python

If you don't have Python installed:

1. Visit https://www.python.org/downloads/
2. Download Python 3.9 or later
3. Run the installer
4. **IMPORTANT**: Check "Add Python to PATH" during installation
5. Click "Install Now"
6. Wait for installation to complete

**Verify Installation:**
```powershell
python --version
pip --version
```

Both should show version numbers. If not, add Python to PATH manually:
- Search "Environment Variables" in Windows
- Click "Edit the system environment variables"
- Click "Environment Variables"
- Under "System variables", find or create "Path"
- Add Python installation directory (usually `C:\Users\YourName\AppData\Local\Programs\Python\Python311`)

### 3. Install WP-CLI

If you don't have WP-CLI:

1. Visit https://wp-cli.org/#installing
2. Follow Windows installation instructions
3. Download the `.phar` file or use the Windows executable installer
4. Place `wp.exe` in a folder on your PATH

**Verify Installation:**
```powershell
wp --info
```

Should show WordPress CLI version and information.

### 4. Install Python Dependencies

Open PowerShell and navigate to the application folder:

```powershell
cd "C:\path\to\WP-Plugin-Review-Assistant"
pip install -r requirements.txt
```

**Expected Output:**
```
Successfully installed PySide6-6.X.X requests-2.X.X jinja2-3.X.X
```

If you see errors:
- Try: `pip install --upgrade pip`
- Then run the install command again

### 5. Verify Installation

Test that everything is working:

```powershell
cd "C:\path\to\WP-Plugin-Review-Assistant"
python main.py
```

The application window should open. If you see any errors, refer to the Troubleshooting section below.

## Running the Application

### Option 1: Quick Launch (Recommended)
Double-click `run.bat` in the folder after installing dependencies. It launches the application with the configured `python` command.

### Option 2: PowerShell
```powershell
cd "C:\path\to\WP-Plugin-Review-Assistant"
python main.py
```

### Option 3: Command Prompt
```cmd
cd "C:\path\to\WP-Plugin-Review-Assistant"
python main.py
```

## Building Standalone Executable

### Prerequisites
- Python and all dependencies installed
- PyInstaller: `pip install pyinstaller`

### Build Steps

1. Open PowerShell in the application folder
2. Run the build script:
   ```powershell
   .\build.ps1
   ```

3. Wait for build to complete (may take 2-5 minutes)
4. Find the executable in `dist\WP-Plugin-Review-Assistant.exe`

**Note**: Standalone executable requires ~400MB disk space but doesn't require Python installed on target machines.

## Troubleshooting

### "Python not found"
**Problem**: `python` command not recognized

**Solutions**:
1. Verify installation: `python --version`
2. Add to PATH (see Installation Step 2)
3. Reinstall Python ensuring "Add to PATH" is checked
4. Use full path: `C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe main.py`

### "ModuleNotFoundError: No module named 'PySide6'"
**Problem**: Dependencies not installed

**Solutions**:
1. Run: `pip install -r requirements.txt`
2. Verify pip: `pip --version`
3. Try: `pip install --upgrade pip`
4. Try again: `pip install -r requirements.txt`

If still failing:
```powershell
pip install PySide6 requests jinja2
```

### "wp command not found" or "WP-CLI not detected"
**Problem**: WP-CLI not installed or not in PATH

**Solutions**:
1. Verify WP-CLI: `wp --info`
2. Install WP-CLI: https://wp-cli.org/#installing
3. Add to PATH:
   - Find wp.exe location
   - Add folder to System PATH environment variable
   - Restart PowerShell

### "No LocalWP sites found"
**Problem**: LocalWP not installed or sites in unexpected location

**Solutions**:
1. Verify LocalWP: Check `C:\Users\<username>\Local Sites\`
2. Ensure WordPress site running in LocalWP
3. Use manual path selection in application
4. Check LocalWP installation location

### "Plugin Check installation fails"
**Problem**: Plugin Check can't install from wp.org

**Solutions**:
1. Verify internet connection
2. Ensure target WordPress site is running
3. Check WP-CLI can connect: `wp --info` from site root
4. Try manual install:
   ```powershell
   cd "path\to\wordpress"
   wp plugin install plugin-check --activate
   ```

### Application starts but no sites appear
**Problem**: LocalWP sites not detected

**Solutions**:
1. Manually browse to WordPress root in "Site Configuration"
2. Verify path contains: `wp-config.php`, `wp-content`, `wp-admin`, `wp-includes`
3. Check LocalWP site is running (green indicator in LocalWP)

### "Permission denied" or access errors
**Problem**: Insufficient permissions

**Solutions**:
1. Run PowerShell as Administrator
2. Ensure LocalWP site files are readable
3. Check Windows file permissions on plugin folder

### Slow performance during analysis
**Problem**: Analysis taking too long

**Reasons**:
1. Large plugins (100+ MB): Normal behavior
2. First run: Plugin Check download can be slow
3. System resources: Low memory available

**Mitigation**:
1. Close other applications
2. Ensure LocalWP site is responsive
3. Wait for completion (may take 5-10 minutes for large plugins)

### "ConnectionError" or network errors
**Problem**: Can't connect to WordPress site

**Solutions**:
1. Ensure LocalWP site is running
2. Verify site URL is accessible
3. Check Windows Firewall isn't blocking
4. Restart LocalWP if needed

## Advanced Configuration

### Using Custom PHP Binary

If PHP auto-detection fails, create a `.env` file:
```
PHP_BINARY=C:\path\to\php.exe
WP_CLI_PHP=C:\path\to\php.exe
```

### Custom Analysis Rules

Edit `src/analysis/agents_rules_analyzer.py` to add custom patterns:
```python
CUSTOM_PATTERNS = {
    'my_pattern': {
        'pattern': r'your_regex_here',
        'severity': IssueSeverity.HIGH,
        'message': 'Description of the issue',
    },
}
```

## Next Steps

1. **First Run**: Load a test plugin to familiarize with the interface
2. **Documentation**: Read README.md for detailed feature documentation
3. **Reporting**: Generate HTML report for sharing with team
4. **Integration**: Copy the generated Codex prompt for automated fixes
5. **Build**: Create standalone executable for distribution if needed

## Getting Help

- Check `wp_plugin_review.log` for detailed error messages
- Review application output messages during analysis
- Verify all system requirements are met
- Ensure LocalWP site is running and accessible

## Uninstallation

To remove the application:
1. Delete the WP Plugin Review Assistant folder
2. No Windows registry entries or system modifications made
3. Optional: Remove dependencies with `pip uninstall -r requirements.txt`

---

**Version**: 1.0.0  
**Last Updated**: 2026-06-09
