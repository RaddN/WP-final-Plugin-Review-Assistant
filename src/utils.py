"""Utility functions and helpers."""
import os
import sys
import logging
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure logging."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('wp_plugin_review.log'),
        ]
    )
    return logging.getLogger('WPPluginReview')


logger = setup_logging()


def normalize_path(path: str) -> Path:
    """Normalize and expand a filesystem path."""
    return Path(path).expanduser().resolve()


def is_valid_wordpress_root(path: Path) -> Tuple[bool, str]:
    """Check if a path is a valid WordPress root directory."""
    required_dirs = {'wp-content', 'wp-admin', 'wp-includes'}
    required_files = {'wp-config.php', 'wp-load.php'}

    if not path.exists():
        return False, f"Path does not exist: {path}"

    if not path.is_dir():
        return False, f"Path is not a directory: {path}"

    missing_dirs = [d for d in required_dirs if not (path / d).is_dir()]
    missing_files = [f for f in required_files if not (path / f).is_file()]

    if missing_dirs or missing_files:
        missing = missing_dirs + missing_files
        return False, f"Missing WordPress files/dirs: {', '.join(missing)}"

    return True, "Valid WordPress installation"


def find_localwp_sites() -> list:
    """Auto-detect LocalWP site paths."""
    sites = []
    base_path = Path.home() / "Local Sites"

    if not base_path.exists():
        logger.warning(f"LocalWP base path not found: {base_path}")
        return sites

    try:
        for site_dir in base_path.iterdir():
            if site_dir.is_dir():
                wp_root = site_dir / "app" / "public"
                if wp_root.exists():
                    is_valid, msg = is_valid_wordpress_root(wp_root)
                    if is_valid:
                        sites.append({
                            'name': site_dir.name,
                            'path': str(wp_root),
                        })
    except Exception as e:
        logger.error(f"Error scanning LocalWP sites: {e}")

    return sites


def create_temp_directory() -> Path:
    """Create a temporary directory for plugin extraction."""
    temp_dir = Path(tempfile.mkdtemp(prefix="wp_plugin_review_"))
    logger.debug(f"Created temp directory: {temp_dir}")
    return temp_dir


def cleanup_temp_directory(path: Path) -> bool:
    """Clean up temporary directory."""
    try:
        if path.exists():
            shutil.rmtree(path)
            logger.debug(f"Cleaned up temp directory: {path}")
            return True
    except Exception as e:
        logger.error(f"Error cleaning up temp directory {path}: {e}")
    return False


def detect_php_binary(wp_root: Path) -> Optional[str]:
    """Try to detect PHP binary from LocalWP or system."""
    # Try LocalWP conventions first
    wp_root = normalize_path(str(wp_root))

    # Check LocalWP PHP locations
    localwp_php_paths = [
        wp_root.parent.parent / "conf" / "php" / "php-*/bin/php",
        wp_root.parent.parent / "conf" / "php" / "*/bin/php",
    ]

    for pattern_path in localwp_php_paths:
        matching_paths = list(pattern_path.parent.glob("php*/bin/php"))
        if matching_paths:
            php_binary = str(matching_paths[0])
            logger.debug(f"Found LocalWP PHP: {php_binary}")
            return php_binary

    # Try system PHP
    php_paths = [
        shutil.which("php"),
        "C:\\php\\php.exe",
        "C:\\Program Files\\php\\php.exe",
    ]

    for php_path in php_paths:
        if php_path and Path(php_path).exists():
            logger.debug(f"Found system PHP: {php_path}")
            return php_path

    logger.warning("Could not detect PHP binary")
    return None


def clean_batch_output(text: str) -> str:
    """Clean Windows batch script wrappers like @echo off from output."""
    if not text:
        return text
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "@echo off":
            continue
        if "wp-cli.phar" in stripped:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def run_command(
    cmd: list,
    cwd: Optional[Path] = None,
    timeout: int = 30,
) -> Tuple[bool, str, str]:
    """Run a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = clean_batch_output(result.stdout)
        stderr = clean_batch_output(result.stderr)
        return result.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)


def validate_zip_file(zip_path: Path) -> Tuple[bool, str]:
    """Validate a ZIP file for safety."""
    import zipfile

    if not zip_path.exists():
        return False, "ZIP file does not exist"

    if not zipfile.is_zipfile(zip_path):
        return False, "File is not a valid ZIP archive"

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for path traversal attempts
            for name in zf.namelist():
                if name.startswith('/') or '..' in name:
                    return False, f"Unsafe path in archive: {name}"
    except Exception as e:
        return False, f"Error reading ZIP: {e}"

    return True, "ZIP file is valid"


def is_hidden_or_dot(path: Path, root_path: Path) -> bool:
    """Check if a path or any of its parents (up to root_path) is hidden or starts with a dot."""
    try:
        rel_parts = path.relative_to(root_path).parts
        if any(part.startswith('.') or part == "__MACOSX" for part in rel_parts):
            return True
    except ValueError:
        if any(part.startswith('.') or part == "__MACOSX" for part in path.parts):
            return True

    try:
        import ctypes
        current = path
        while current != root_path and current != current.parent:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(current))
            if attrs != -1 and (attrs & 2):  # FILE_ATTRIBUTE_HIDDEN is 2
                return True
            current = current.parent
    except Exception:
        pass
    return False

