# dependency_validator.py - A tool to validate dependency issues
import os
import json
import re
from pathlib import Path

def validate_dependency_report(report_path):
    """Validate a dependency report by checking if issues actually exist"""
    # Load the report
    with open(report_path) as f:
        report = json.load(f)
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(report_path)))
    
    # Validate each issue
    valid_issues = []
    false_positives = []
    
    for issue in report.get('issues', []):
        if issue.get('type') == 'missing_include':
            file_path = issue.get('file')
            include_file = issue.get('message', '').split("'")[1]
            
            # Check if the file exists
            full_path = os.path.join(project_root, file_path)
            if not os.path.exists(full_path):
                # File doesn't exist, so issue is invalid
                false_positives.append({
                    'issue': issue,
                    'reason': 'File not found'
                })
                continue
            
            # Check if include already exists
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            if f'#include "{include_file}"' in content or f'#include <{include_file}>' in content:
                # Include already exists, so issue is a false positive
                false_positives.append({
                    'issue': issue,
                    'reason': 'Include already exists'
                })
            else:
                # Issue is valid
                valid_issues.append(issue)
    
    # Create validated report
    validated_report = {
        'valid_issues': valid_issues,
        'false_positives': false_positives,
        'total_issues': len(report.get('issues', [])),
        'valid_count': len(valid_issues),
        'false_positive_count': len(false_positives)
    }
    
    # Save validated report
    validated_path = os.path.join(os.path.dirname(report_path), 'validated_dependency_report.json')
    with open(validated_path, 'w') as f:
        json.dump(validated_report, f, indent=2)
    
    print(f"Validation complete: {len(valid_issues)} valid issues, {len(false_positives)} false positives")
    print(f"Validated report saved to {validated_path}")
    
    return validated_report

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        report_path = os.path.join(project_root, "dependency_report.json")
    
    validate_dependency_report(report_path)