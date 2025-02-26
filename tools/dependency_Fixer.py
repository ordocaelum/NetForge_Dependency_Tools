# tools/dependency_fixer.py - Simplified for local use
import os
import json
import re
import sys
from pathlib import Path

print("Script execution started")

class DependencyFixer:
    def __init__(self, report_path, project_root):
        self.project_root = Path(project_root)
        with open(report_path) as f:
            self.report = json.load(f)
        self.fixed_issues = 0
        self.engine_path = self._detect_engine_path()
        
    def _detect_engine_path(self):
        """Auto-detect Unreal Engine installation path"""
        # Check common installation locations with UE5.5 first
        potential_paths = [
            "H:/Games/UE_5.5",
            "C:/Epic Games/UE_5.5",
            "D:/Program Files/Epic Games/UE_5.5",
            # Fallbacks to other versions
            "C:/Program Files/Epic Games/UE_5.3",
            "C:/Program Files/Epic Games/UE_5.2",
            os.environ.get("UNREAL_ENGINE_DIR", "")
        ]
        
        for path in potential_paths:
            if path and os.path.exists(path):
                print(f"✅ Found Unreal Engine at: {path}")
                return Path(path)
                
        print("⚠️ Could not auto-detect Unreal Engine path. Some fixes may not be applied.")
        return None
    
    def fix_all_issues(self):
        """Fix all dependency issues in the report"""
        print(f"🔍 Found {len(self.report['issues'])} issues to fix")
        
        # Process each issue
        for issue in self.report['issues']:
            if issue['type'] == 'missing_include':
                self._fix_missing_include(issue['file'], issue['message'].split("'")[1])
            
        # Update build files to ensure correct include paths
        self._update_build_files()
        
        print(f"✅ Fixed {self.fixed_issues} dependency issues")
        return self.fixed_issues
    
    def _fix_missing_include(self, file_path, include_file):
        """Fix a missing include in a file"""
        full_path = self.project_root / file_path
        if not full_path.exists():
            print(f"⚠️ File not found: {full_path}")
            return
                
        try:
            # Read the file content
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                    
            # Check if include already exists
            if f'#include "{include_file}"' in content or f'#include <{include_file}>' in content:
                print(f"⚠️ Include '{include_file}' already exists in {file_path}")
                return
                    
            # Find the correct include path - THIS IS THE CRITICAL POINT
            corrected_include = self._find_correct_include_path(include_file, file_path)
            print(f"DEBUG: For {include_file} in {file_path}, corrected path is: {corrected_include}")
            
            if not corrected_include:
                print(f"⚠️ Could not determine correct path for {include_file}")
                return
                    
            # Add the include at the top of the file after existing includes
            include_section_match = re.search(r'((?:#include\s+[<"].*[>"]\s*\n)+)', content)
            if include_section_match:
                section_end = include_section_match.end()
                new_content = (content[:section_end] + 
                            f'#include "{corrected_include}"\n' + 
                            content[section_end:])
            else:
                new_content = f'#include "{corrected_include}"\n' + content
                
            # Only write if content actually changed
            if new_content != content:
                print(f"✓ Writing changes to {file_path}")
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                self.fixed_issues += 1
                print(f"✓ Added include '{corrected_include}' to {file_path}")
            else:
                print(f"⚠️ No changes needed for {file_path}")
                
        except Exception as e:
            print(f"❌ Error fixing {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _find_correct_include_path(self, include_file, source_file):
        """Find the correct path for an include file"""
        # Handle common engine includes
        engine_includes = {
            "CoreMinimal.h": "CoreMinimal.h",
            "Modules/ModuleManager.h": "Modules/ModuleManager.h",
            "UObject/NoExportTypes.h": "UObject/NoExportTypes.h",
            "UObject/Interface.h": "UObject/Interface.h",
            "Components/ActorComponent.h": "Components/ActorComponent.h",
            "OnlineSubsystem.h": "OnlineSubsystem.h",
            "OnlineSessionSettings.h": "OnlineSessionSettings.h",
            "OnlineSubsystemTypes.h": "OnlineSubsystemTypes.h",
            "HAL/ThreadSafeBool.h": "HAL/ThreadSafeBool.h",
            "Templates/SharedPointer.h": "Templates/SharedPointer.h",
            "Containers/Ticker.h": "Containers/Ticker.h"
        }
        
        if include_file in engine_includes:
            return engine_includes[include_file]
            
        # Handle generated headers
        if include_file.endswith('.generated.h'):
            return None  # These are auto-generated
            
        # Handle project-specific includes based on analysis of your report
        if include_file == "NetForgeTypes.h":
            if "Plugins" in source_file:
                return "NetForgeUE/Public/Core/NetForgeTypes.h"
            else:
                return "Core/NetForgeTypes.h"
                
        if include_file == "INetForgeMonitoring.h":
            if "Plugins" in source_file:
                return "Interfaces/INetForgeMonitoring.h"
            
        if include_file == "INetForgeSessions.h":
            if "Plugins" in source_file:
                return "Interfaces/INetForgeSessions.h"
                
        # Try to find the file in the project structure
        for root_dir in ["Source", "Plugins"]:
            for path in Path(self.project_root / root_dir).glob(f"**/{include_file}"):
                rel_path = os.path.relpath(path, (self.project_root / source_file).parent)
                return rel_path.replace('\\', '/')
                
        # If we can't find it, return the original as fallback
        return include_file
    
    def _update_build_files(self):
        """Update Build.cs files to add missing include paths"""
        build_files = []
        for ext in ["*.Build.cs", "*.build.cs"]:
            build_files.extend(self.project_root.glob(f"**/{ext}"))
            
        for build_file in build_files:
            try:
                with open(build_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                # Check if we need to add engine dependencies
                if "PublicDependencyModuleNames" in content and not all(dep in content for dep in ["Core", "CoreUObject", "Engine"]):
                    match = re.search(r'PublicDependencyModuleNames\.AddRange\(\s*new\s+string\[\]\s*\{([^}]*)\}\s*\)', content)
                    if match:
                        deps_section = match.group(1)
                        new_deps = deps_section.rstrip()
                        if not "Core" in new_deps:
                            new_deps += ',\n            "Core"'
                        if not "CoreUObject" in new_deps:
                            new_deps += ',\n            "CoreUObject"'
                        if not "Engine" in new_deps:
                            new_deps += ',\n            "Engine"'
                        if "Sessions" in str(build_file) and not "OnlineSubsystem" in new_deps:
                            new_deps += ',\n            "OnlineSubsystem"'
                            
                        content = content.replace(deps_section, new_deps)
                        
                        with open(build_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                            
                        self.fixed_issues += 1
                        print(f"✓ Updated module dependencies in {build_file.name}")
                
            except Exception as e:
                print(f"❌ Error updating {build_file}: {str(e)}")