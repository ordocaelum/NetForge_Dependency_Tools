#!/usr/bin/env python3
# unreal_dependency_crawler.py
# A DevOps tool for analyzing Unreal Engine project dependencies

import os
import re
import sys
import json
import argparse
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

class UnrealDependencyCrawler:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.dependency_graph = nx.DiGraph()
        self.include_paths = []
        self.module_map = {}
        self.type_definitions = {}
        self.type_references = {}
        self.issues = []
        self.file_content_cache = {}  # Cache file contents to avoid repeated reads
        
        # Regex patterns
        self.include_pattern = re.compile(r'#include\s+"([^"]+)"')
        self.angle_include_pattern = re.compile(r'#include\s+<([^>]+)>')  # NEW: Also match angle bracket includes
        self.generated_pattern = re.compile(r'#include\s+"([^"]+\.generated\.h)"')
        self.class_pattern = re.compile(r'(UCLASS|USTRUCT|UENUM)\s*\([^)]*\)\s*\n*\s*(class|struct|enum\s+class)\s+(\w+)')
        self.interface_pattern = re.compile(r'class\s+\w+_API\s+I(\w+)')
        self.override_pattern = re.compile(r'virtual\s+\w+\s+(\w+)\s*\([^)]*\)\s*override')
        self.api_macro_pattern = re.compile(r'(\w+)_API')
        
    def scan_build_files(self):
        """Scan all Build.cs files to extract module dependencies and include paths"""
        print("🔍 Scanning Build.cs files...")
        
        for build_file in self.project_root.rglob("*.Build.cs"):
            module_name = build_file.stem
            print(f"  📦 Found module: {module_name}")
            
            with open(build_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Extract module dependencies
                dependency_pattern = re.compile(r'PublicDependencyModuleNames.AddRange\(\s*new string\[\] \{([^}]+)\}\s*\)')
                matches = dependency_pattern.findall(content)
                if matches:
                    for match in matches:
                        modules = re.findall(r'"([^"]+)"', match)
                        for dep_module in modules:
                            self.dependency_graph.add_edge(module_name, dep_module)
                            print(f"    ↔️ Dependency: {module_name} -> {dep_module}")
                
                # Extract include paths
                include_path_pattern = re.compile(r'PublicIncludePaths.AddRange\(\s*new string\[\] \{([^}]+)\}\s*\)')
                matches = include_path_pattern.findall(content)
                if matches:
                    for match in matches:
                        paths = re.findall(r'"([^"]+)"', match)
                        for path in paths:
                            # Resolve relative paths
                            if "ModuleDirectory" in path:
                                path = path.replace("ModuleDirectory", str(build_file.parent))
                            self.include_paths.append(path)
                            print(f"    📁 Include path: {path}")
    
    def scan_header_files(self):
        """Scan all header files to build dependency graph and type definitions"""
        print("\n🔍 Scanning header files...")
        
        for header_file in self.project_root.rglob("*.h"):
            if "Intermediate" in str(header_file) or "Binaries" in str(header_file):
                continue
                
            relative_path = header_file.relative_to(self.project_root)
            print(f"  📄 Analyzing: {relative_path}")
            
            try:
                # Cache file content for later use
                content = self._get_file_content(header_file)
                self.file_content_cache[str(relative_path)] = content
                
                # Find module API macro
                api_matches = self.api_macro_pattern.findall(content)
                if api_matches:
                    module_name = api_matches[0]
                    self.module_map[str(relative_path)] = module_name
                
                # Find includes
                includes = self.include_pattern.findall(content)
                # Also find angle bracket includes
                angle_includes = self.angle_include_pattern.findall(content)
                all_includes = includes + angle_includes
                
                for include in all_includes:
                    self.dependency_graph.add_edge(str(relative_path), include)
                    print(f"    ↔️ Include: {include}")
                
                # Find UE type definitions
                type_matches = self.class_pattern.findall(content)
                for _, type_kind, type_name in type_matches:
                    self.type_definitions[type_name] = str(relative_path)
                    print(f"    🏷️ Type defined: {type_name}")
                
                # Find interface definitions
                interface_matches = self.interface_pattern.findall(content)
                for interface_name in interface_matches:
                    full_name = f"I{interface_name}"
                    self.type_definitions[full_name] = str(relative_path)
                    print(f"    🔌 Interface defined: {full_name}")
                
                # Find override methods
                override_matches = self.override_pattern.findall(content)
                for method_name in override_matches:
                    if "Implementation" in method_name:
                        base_method = method_name.replace("_Implementation", "")
                        self.issues.append({
                            "file": str(relative_path),
                            "type": "interface_mismatch",
                            "message": f"Method '{method_name}' contains '_Implementation' suffix but uses override - interface method should be '{base_method}'"
                        })
            except Exception as e:
                print(f"    ❌ Error processing {relative_path}: {e}")
    
    def _get_file_content(self, file_path):
        """Get file content with error handling"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"    ⚠️ Error reading {file_path}: {e}")
            return ""
    
    def _check_include_already_exists(self, file_path, include_name):
        """Check if an include already exists in the file - NEW METHOD"""
        if file_path not in self.file_content_cache:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.file_content_cache[file_path] = self._get_file_content(full_path)
            else:
                return False
        
        content = self.file_content_cache[file_path]
        
        # Check for both quote and angle bracket includes
        return f'#include "{include_name}"' in content or f'#include <{include_name}>' in content
    
    def validate_dependencies(self):
        """Validate all dependencies and identify issues"""
        print("\n🔍 Validating dependencies...")
        
        for node in self.dependency_graph.nodes():
            if not node.endswith('.h'):
                continue  # Skip non-header nodes
                
            for dependency in list(self.dependency_graph.successors(node)):
                # CRITICAL FIX: First check if the include already exists in the file
                if self._check_include_already_exists(node, dependency):
                    print(f"  ✅ Include already exists: {node} -> {dependency}")
                    continue
                
                # Check if dependency file exists directly
                dependency_path = self.project_root / dependency
                if not dependency_path.exists():
                    # Check if it exists in any include path
                    found = False
                    for include_path in self.include_paths:
                        test_path = Path(include_path) / dependency
                        if test_path.exists():
                            found = True
                            break
                    
                    if not found:
                        self.issues.append({
                            "file": node,
                            "type": "missing_include",
                            "message": f"Cannot find include file: '{dependency}'"
                        })
                        print(f"  ❌ Missing include: {node} -> {dependency}")
    
    def detect_circular_dependencies(self):
        """Detect circular dependencies in the include graph"""
        print("\n🔍 Checking for circular dependencies...")
        
        try:
            cycles = list(nx.simple_cycles(self.dependency_graph))
            for cycle in cycles:
                if len(cycle) > 1:  # Ignore self-references
                    cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
                    self.issues.append({
                        "type": "circular_dependency",
                        "message": f"Circular dependency detected: {cycle_str}"
                    })
                    print(f"  ⭕ Circular dependency: {cycle_str}")
        except Exception as e:
            print(f"  ⚠️ Error detecting cycles: {e}")
    
    def generate_report(self):
        """Generate a detailed report of findings"""
        report = {
            "project": str(self.project_root),
            "modules": len(self.module_map),
            "types_defined": len(self.type_definitions),
            "include_paths": self.include_paths,
            "issues": self.issues
        }
        
        # Group issues by file
        issues_by_file = defaultdict(list)
        for issue in self.issues:
            file_name = issue.get("file", "project")
            issues_by_file[file_name].append(issue)
        
        # Print summary
        print("\n📊 Dependency Analysis Summary")
        print(f"  📦 Modules found: {report['modules']}")
        print(f"  🏷️ Type definitions: {report['types_defined']}")
        print(f"  ❌ Issues detected: {len(self.issues)}")
        
        # Print issues by file
        if self.issues:
            print("\n❌ Issues by file:")
            for file, file_issues in issues_by_file.items():
                print(f"  📄 {file}:")
                for issue in file_issues:
                    print(f"    • {issue['message']}")
        
        # Save report to file
        with open("dependency_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print("\n✅ Report saved to dependency_report.json")
        
        return report
    
    def visualize_dependencies(self):
        """Create a visual representation of dependencies"""
        print("\n🎨 Generating dependency visualization...")
        
        # Create a simplified graph for visualization
        vis_graph = nx.DiGraph()
        
        # Add module dependencies
        for source, target in self.dependency_graph.edges():
            if source in self.module_map and target in self.module_map:
                vis_graph.add_edge(self.module_map[source], self.module_map[target])
        
        # Draw the graph
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(vis_graph)
        nx.draw(vis_graph, pos, with_labels=True, node_color="lightblue", 
                node_size=2000, font_size=10, arrows=True)
        plt.title("Module Dependencies")
        plt.savefig("dependency_graph.png")
        print("✅ Visualization saved to dependency_graph.png")
    
    def run_analysis(self):
        """Run the complete dependency analysis"""
        self.scan_build_files()
        self.scan_header_files()
        self.validate_dependencies()
        self.detect_circular_dependencies()
        report = self.generate_report()
        self.visualize_dependencies()
        
        return len(self.issues) == 0

def main():
    parser = argparse.ArgumentParser(description="Unreal Engine Dependency Crawler")
    parser.add_argument("--project-dir", default=".", help="Path to the Unreal project directory")
    args = parser.parse_args()
    
    print("🚀 Starting Unreal Engine Dependency Crawler")
    print(f"📁 Project directory: {args.project_dir}")
    
    crawler = UnrealDependencyCrawler(args.project_dir)
    success = crawler.run_analysis()
    
    if success:
        print("\n✅ Dependency analysis completed successfully - no issues found!")
        return 0
    else:
        print("\n⚠️ Dependency analysis completed with issues. See report for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())