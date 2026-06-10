"""Utility functions and helpers."""
import json
import os
import re
import sys
import logging
import shutil
import tempfile
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


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
    wp_root = normalize_path(str(wp_root))

    runtime = detect_localwp_runtime(wp_root)
    if runtime.get("php_binary"):
        return str(runtime["php_binary"])

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


def detect_localwp_runtime(wp_root: Path) -> Dict[str, Any]:
    """Resolve the LocalWP site ID, PHP binary, php.ini, and MySQL port."""
    wp_root = normalize_path(str(wp_root))
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    local_data = appdata / "Local"
    sites_file = local_data / "sites.json"
    if not sites_file.is_file():
        return {}

    try:
        with open(sites_file, "r", encoding="utf-8") as handle:
            sites = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Could not read LocalWP sites.json: %s", exc)
        return {}

    site_root = wp_root
    if wp_root.name.lower() == "public" and wp_root.parent.name.lower() == "app":
        site_root = wp_root.parent.parent

    for site in sites.values():
        configured_path = site.get("path")
        if not configured_path:
            continue
        try:
            configured_root = normalize_path(str(configured_path))
        except OSError:
            continue
        if os.path.normcase(str(configured_root)) != os.path.normcase(str(site_root)):
            continue

        site_id = str(site.get("id", ""))
        services = site.get("services", {})
        php_service = services.get("php", {})
        mysql_service = services.get("mysql", {})
        php_version = str(php_service.get("version", ""))
        mysql_ports = mysql_service.get("ports", {}).get("MYSQL", [])
        mysql_port = mysql_ports[0] if mysql_ports else None

        php_binary = None
        service_root = local_data / "lightning-services"
        if php_version and service_root.is_dir():
            service_dirs = sorted(service_root.glob(f"php-{php_version}+*"), reverse=True)
            for service_dir in service_dirs:
                for relative in [
                    Path("bin") / "win64" / "php.exe",
                    Path("bin") / "win32" / "php.exe",
                ]:
                    candidate = service_dir / relative
                    if candidate.is_file():
                        php_binary = candidate
                        break
                if php_binary:
                    break

        php_ini = local_data / "run" / site_id / "conf" / "php" / "php.ini"
        return {
            "site_id": site_id,
            "php_binary": str(php_binary) if php_binary else None,
            "php_ini": str(php_ini) if php_ini.is_file() else None,
            "mysql_port": mysql_port,
        }

    return {}


def clean_command_output(text: str) -> str:
    """Remove command-wrapper noise that can corrupt machine-readable output."""
    if not text:
        return text
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "@echo off":
            continue
        if re.match(r"^(?:PHP )?Warning: PHP Startup:.* in Unknown on line 0$", stripped):
            logger.debug("Ignoring non-fatal PHP startup warning: %s", stripped)
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def run_command(
    cmd: list,
    cwd: Optional[Path] = None,
) -> Tuple[bool, str, str]:
    """Run a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        stdout = clean_command_output(result.stdout)
        stderr = clean_command_output(result.stderr)
        return result.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)


def validate_zip_file(zip_path: Path) -> Tuple[bool, str]:
    """Validate a ZIP file for safety."""
    if not zip_path.exists():
        return False, "ZIP file does not exist"

    if not zipfile.is_zipfile(zip_path):
        return False, "File is not a valid ZIP archive"

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            if len(zf.infolist()) > 20000:
                return False, "ZIP archive contains too many files"

            total_size = 0
            for member in zf.infolist():
                is_valid, message = _validate_zip_member(member)
                if not is_valid:
                    return False, message
                total_size += member.file_size
                if total_size > 2 * 1024 * 1024 * 1024:
                    return False, "ZIP archive expands beyond the 2 GB safety limit"
    except Exception as e:
        return False, f"Error reading ZIP: {e}"

    return True, "ZIP file is valid"


def _validate_zip_member(member: zipfile.ZipInfo) -> Tuple[bool, str]:
    """Validate one ZIP member path and reject links."""
    normalized = member.filename.replace("\\", "/")
    if "\x00" in normalized:
        return False, f"Unsafe null byte in archive path: {member.filename}"

    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return False, f"Unsafe absolute path in archive: {member.filename}"
    if any(part == ".." for part in parts):
        return False, f"Unsafe path traversal in archive: {member.filename}"

    unix_mode = (member.external_attr >> 16) & 0xFFFF
    if (unix_mode & 0o170000) == 0o120000:
        return False, f"Symbolic links are not allowed in plugin ZIPs: {member.filename}"

    return True, ""


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    """Extract a validated ZIP without allowing writes outside destination."""
    destination = normalize_path(str(destination))
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            is_valid, message = _validate_zip_member(member)
            if not is_valid:
                raise ValueError(message)

            normalized = member.filename.replace("\\", "/")
            relative = Path(*[part for part in normalized.split("/") if part not in ("", ".")])
            if not relative.parts:
                continue

            target = (destination / relative).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError(f"Unsafe extraction target: {member.filename}") from exc

            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


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
