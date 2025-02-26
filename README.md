# NetForge_Dependency_Tools
Tools for managing dependencies in Unreal Engine projects- not just using NetForge

# NetForge Dependency Tools

A collection of tools for managing dependencies in Unreal Engine projects.

## 🛠️ Tools Included

- **unreal_dependency_crawler.py**: Analyzes Unreal Engine projects for dependency issues
- **dependency_fixer.py**: Automatically fixes dependency issues identified by the crawler
- **dependency_validator.py**: Validates dependency reports to filter out false positives

## 🚀 Quick Start

```bash
# Run dependency analysis
python tools/unreal_dependency_crawler.py --project-dir /path/to/unreal/project

# Fix identified issues
python tools/dependency_fixer.py

# OR use the all-in-one script
./tools/run-analysis.sh /path/to/unreal/project

📋 Requirements

Python 3.8+
NetworkX (pip install networkx)
Matplotlib (pip install matplotlib)


📖 Documentation

Each tool can be run with the --help flag for detailed usage information.


🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.