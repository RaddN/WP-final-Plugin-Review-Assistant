import sys
import os
import json
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.settings_manager import SettingsManager
from core.plugin_detector import PluginDetector
from core.localwp_validator import LocalWPValidator
from core.review_orchestrator import ReviewOrchestrator
from report_generator import ReportGenerator

def main():
    settings = SettingsManager()
    plugin_path = settings.get("last_plugin_path")
    site_path = settings.get("last_site_path")
    
    print(f"Plugin Path: {plugin_path}")
    print(f"Site Path: {site_path}")
    
    if not plugin_path or not site_path:
        print("Error: last_plugin_path or last_site_path not set in settings.json.")
        return
        
    print("\nDetecting plugin...")
    detector = PluginDetector(plugin_path)
    success, metadata, error = detector.detect()
    if not success or not metadata:
        print(f"Error detecting plugin: {error}")
        return
    print(f"Plugin detected: {metadata.name} v{metadata.version}")
    
    print("\nSelecting site...")
    validator = LocalWPValidator()
    site = validator.select_site_by_path(site_path)
    if not site:
        print(f"Error: Path {site_path} is not a valid WordPress site.")
        return
    print(f"Site selected: {site.name}")
    
    print("\nRunning review...")
    orchestrator = ReviewOrchestrator(settings)
    
    try:
        result = orchestrator.run(metadata, site)
        print("\nReview run completed successfully!")
        print(f"Total issues: {len(result.review.all_issues)}")
        print(f"AI Available: {result.ai_available}")
        print(f"AI Summary length: {len(result.review.ai_summary) if result.review.ai_summary else 0}")
        
        html_out = "scratch_report.html"
        print(f"\nGenerating HTML report to {html_out}...")
        rg = ReportGenerator(result.review, result.checklist)
        rg.generate_html_report(html_out)
        
        print(f"Report size: {os.path.getsize(html_out)} bytes")
        
    except Exception as e:
        print(f"\nError running orchestrator: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
