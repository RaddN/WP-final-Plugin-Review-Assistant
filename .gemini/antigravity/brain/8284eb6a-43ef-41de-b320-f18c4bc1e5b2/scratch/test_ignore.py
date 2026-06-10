import sys
import os
from pathlib import Path
import ctypes

# Add src to python path
sys.path.insert(0, "C:/Users/GM Team/OneDrive/Desktop/WP-Plugin-Review-Assistant/src")

from utils import is_hidden_or_dot
from analysis.agents_rules_analyzer import AgentsRulesAnalyzer

def test_ignore():
    temp_dir = Path(__file__).parent / "test_plugin"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Create normal files
    (temp_dir / "my-plugin.php").write_text("<?php\n/* Plugin Name: Test Plugin */\n// ABSPATH guard\nif ( ! defined( 'ABSPATH' ) ) { exit; }\necho 'Hello';", encoding='utf-8')
    
    # Create dot files and folders
    dot_dir = temp_dir / ".git"
    dot_dir.mkdir(exist_ok=True)
    (dot_dir / "config").write_text("git config", encoding='utf-8')
    (dot_dir / "index.php").write_text("<?php\n// Dot dir php", encoding='utf-8')
    
    (temp_dir / ".env").write_text("SECRET_KEY=12345", encoding='utf-8')
    (temp_dir / ".gitignore").write_text("*.log", encoding='utf-8')
    
    # Create Windows hidden files (if on Windows)
    hidden_dir = temp_dir / "hidden_dir"
    hidden_dir.mkdir(exist_ok=True)
    (hidden_dir / "nested.php").write_text("<?php\n// Hidden nested php", encoding='utf-8')
    
    hidden_file = temp_dir / "hidden_file.php"
    hidden_file.write_text("<?php\n// Hidden file", encoding='utf-8')
    
    # Set Windows hidden attributes
    if os.name == 'nt':
        ctypes.windll.kernel32.SetFileAttributesW(str(hidden_dir), 2)  # FILE_ATTRIBUTE_HIDDEN is 2
        ctypes.windll.kernel32.SetFileAttributesW(str(hidden_file), 2)
        print("Set Windows hidden attributes successfully.")
    
    # Test utils function
    print("Testing is_hidden_or_dot:")
    print(f".env hidden? {is_hidden_or_dot(temp_dir / '.env', temp_dir)}")
    print(f".git/index.php hidden? {is_hidden_or_dot(dot_dir / 'index.php', temp_dir)}")
    print(f"my-plugin.php hidden? {is_hidden_or_dot(temp_dir / 'my-plugin.php', temp_dir)}")
    
    if os.name == 'nt':
        print(f"hidden_dir hidden? {is_hidden_or_dot(hidden_dir, temp_dir)}")
        print(f"hidden_dir/nested.php hidden? {is_hidden_or_dot(hidden_dir / 'nested.php', temp_dir)}")
        print(f"hidden_file.php hidden? {is_hidden_or_dot(hidden_file, temp_dir)}")

    # Test analyzer file collection
    analyzer = AgentsRulesAnalyzer(str(temp_dir))
    php_files = analyzer._collect_files("*.php")
    print("\nCollected files:")
    for f in php_files:
        print(f"- {f.relative_to(temp_dir)}")
        
    # We expect ONLY my-plugin.php to be collected!
    collected_names = [f.name for f in php_files]
    assert "my-plugin.php" in collected_names, "my-plugin.php should be collected!"
    assert "nested.php" not in collected_names, "nested.php (inside hidden dir) should be ignored!"
    assert "hidden_file.php" not in collected_names, "hidden_file.php should be ignored!"
    assert "index.php" not in collected_names, "index.php (inside .git) should be ignored!"
    print("\nTEST PASSED: Only non-dot, non-hidden files were collected!")

    # Cleanup test_plugin folder
    import shutil
    # Reset hidden attributes so we can delete them
    if os.name == 'nt':
        ctypes.windll.kernel32.SetFileAttributesW(str(hidden_dir), 128) # FILE_ATTRIBUTE_NORMAL
        ctypes.windll.kernel32.SetFileAttributesW(str(hidden_file), 128)
    shutil.rmtree(temp_dir)
    print("Cleaned up test plugin folder.")

if __name__ == "__main__":
    test_ignore()
