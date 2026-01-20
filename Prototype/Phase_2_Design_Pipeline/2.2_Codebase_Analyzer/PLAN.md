# 2.2 Codebase Analyzer

## Objective

Create a codebase analyzer that can scan existing projects, detect technologies, extract dependencies, and generate component maps. This enables the Architect to design improvements for existing codebases.

## Files to Create

```
Visual/
├── analyzers/
│   ├── __init__.py
│   ├── scanner.py              # File system scanning
│   ├── dependency_analyzer.py  # Import/dependency detection
│   └── detectors/
│       ├── __init__.py
│       ├── python.py           # Python-specific detection
│       ├── javascript.py       # JS/TS detection
│       └── generic.py          # Fallback detection
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│                CodebaseAnalyzer                   │
├──────────────────────────────────────────────────┤
│ + scan(path) -> AnalysisResult                   │
│ + detect_language(path) -> Language              │
│ + extract_dependencies(files) -> Dependencies    │
│ + find_entry_points() -> List[str]               │
│ + generate_component_map() -> Dict               │
└──────────────────────────────────────────────────┘
         │
         │ uses
         ▼
┌──────────────────────────────────────────────────┐
│              LanguageDetector                     │
├──────────────────────────────────────────────────┤
│ + PythonDetector                                 │
│ + JavaScriptDetector                             │
│ + GenericDetector                                │
└──────────────────────────────────────────────────┘
```

## Implementation

### scanner.py

```python
"""
Codebase Scanner - File system analysis for existing projects.
"""
import os
import glob
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import Counter
import json

@dataclass
class FileInfo:
    path: str
    name: str
    extension: str
    size: int
    lines: int = 0

@dataclass
class AnalysisResult:
    root_path: str
    languages: List[str] = field(default_factory=list)
    file_count: int = 0
    total_lines: int = 0
    files: List[FileInfo] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    components: List[Dict] = field(default_factory=list)
    structure: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'root_path': self.root_path,
            'languages': self.languages,
            'file_count': self.file_count,
            'total_lines': self.total_lines,
            'dependencies': self.dependencies,
            'entry_points': self.entry_points,
            'components': self.components,
            'structure': self.structure
        }

class CodebaseScanner:
    """Scans and analyzes codebases."""

    IGNORE_DIRS = {
        'node_modules', '__pycache__', '.git', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.next', '.nuxt',
        'coverage', '.pytest_cache', '.mypy_cache'
    }

    IGNORE_FILES = {
        '.DS_Store', 'Thumbs.db', '.gitignore', '.env',
        'package-lock.json', 'yarn.lock', 'poetry.lock'
    }

    LANGUAGE_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.jsx': 'JavaScript',
        '.java': 'Java',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.cs': 'C#',
        '.cpp': 'C++',
        '.c': 'C',
        '.swift': 'Swift',
        '.kt': 'Kotlin'
    }

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")

    def scan(self) -> AnalysisResult:
        """Perform full codebase analysis."""
        result = AnalysisResult(root_path=str(self.root_path))

        # Scan files
        result.files = self._scan_files()
        result.file_count = len(result.files)
        result.total_lines = sum(f.lines for f in result.files)

        # Detect languages
        result.languages = self._detect_languages(result.files)

        # Build directory structure
        result.structure = self._build_structure()

        # Extract dependencies based on primary language
        if 'Python' in result.languages:
            result.dependencies.extend(self._extract_python_deps())
            result.entry_points.extend(self._find_python_entry_points())
        if 'JavaScript' in result.languages or 'TypeScript' in result.languages:
            result.dependencies.extend(self._extract_js_deps())
            result.entry_points.extend(self._find_js_entry_points())

        # Generate component suggestions
        result.components = self._suggest_components(result)

        return result

    def _scan_files(self) -> List[FileInfo]:
        """Scan all source files in the codebase."""
        files = []

        for root, dirs, filenames in os.walk(self.root_path):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

            for filename in filenames:
                if filename in self.IGNORE_FILES:
                    continue

                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                if ext in self.LANGUAGE_EXTENSIONS:
                    try:
                        lines = sum(1 for _ in open(filepath, 'r', errors='ignore'))
                    except:
                        lines = 0

                    files.append(FileInfo(
                        path=str(filepath.relative_to(self.root_path)),
                        name=filename,
                        extension=ext,
                        size=filepath.stat().st_size,
                        lines=lines
                    ))

        return files

    def _detect_languages(self, files: List[FileInfo]) -> List[str]:
        """Detect primary languages used."""
        ext_counts = Counter(f.extension for f in files)

        languages = []
        for ext, count in ext_counts.most_common():
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                if lang not in languages:
                    languages.append(lang)

        return languages

    def _build_structure(self) -> Dict:
        """Build directory tree structure."""
        structure = {'name': self.root_path.name, 'type': 'folder', 'children': []}

        for item in sorted(self.root_path.iterdir()):
            if item.name in self.IGNORE_DIRS or item.name.startswith('.'):
                continue

            if item.is_dir():
                child = self._build_dir_structure(item, depth=1)
                if child:
                    structure['children'].append(child)
            elif item.suffix.lower() in self.LANGUAGE_EXTENSIONS:
                structure['children'].append({
                    'name': item.name,
                    'type': 'file',
                    'path': str(item.relative_to(self.root_path))
                })

        return structure

    def _build_dir_structure(self, path: Path, depth: int, max_depth: int = 3) -> Optional[Dict]:
        """Recursively build directory structure."""
        if depth > max_depth:
            return None

        children = []
        for item in sorted(path.iterdir()):
            if item.name in self.IGNORE_DIRS or item.name.startswith('.'):
                continue

            if item.is_dir():
                child = self._build_dir_structure(item, depth + 1, max_depth)
                if child:
                    children.append(child)
            elif item.suffix.lower() in self.LANGUAGE_EXTENSIONS:
                children.append({
                    'name': item.name,
                    'type': 'file',
                    'path': str(item.relative_to(self.root_path))
                })

        if children:
            return {
                'name': path.name,
                'type': 'folder',
                'children': children
            }
        return None

    def _extract_python_deps(self) -> List[str]:
        """Extract Python dependencies from requirements.txt or pyproject.toml."""
        deps = []

        # Check requirements.txt
        req_file = self.root_path / 'requirements.txt'
        if req_file.exists():
            with open(req_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name
                        pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0]
                        deps.append(pkg.strip())

        # Check pyproject.toml
        pyproject = self.root_path / 'pyproject.toml'
        if pyproject.exists():
            # Simple extraction (full TOML parsing would need toml library)
            pass

        return deps

    def _extract_js_deps(self) -> List[str]:
        """Extract JavaScript dependencies from package.json."""
        deps = []

        pkg_file = self.root_path / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file) as f:
                    pkg = json.load(f)
                deps.extend(pkg.get('dependencies', {}).keys())
            except json.JSONDecodeError:
                pass

        return deps

    def _find_python_entry_points(self) -> List[str]:
        """Find Python entry points (main.py, __main__.py, etc.)."""
        entry_points = []

        patterns = ['main.py', 'app.py', '__main__.py', 'cli.py', 'run.py']
        for pattern in patterns:
            matches = list(self.root_path.rglob(pattern))
            for match in matches:
                entry_points.append(str(match.relative_to(self.root_path)))

        return entry_points

    def _find_js_entry_points(self) -> List[str]:
        """Find JavaScript entry points."""
        entry_points = []

        # Check package.json main field
        pkg_file = self.root_path / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file) as f:
                    pkg = json.load(f)
                if 'main' in pkg:
                    entry_points.append(pkg['main'])
            except:
                pass

        # Common patterns
        patterns = ['index.js', 'index.ts', 'app.js', 'app.ts', 'server.js', 'main.js']
        for pattern in patterns:
            matches = list(self.root_path.rglob(pattern))
            for match in matches[:3]:  # Limit results
                entry_points.append(str(match.relative_to(self.root_path)))

        return entry_points

    def _suggest_components(self, result: AnalysisResult) -> List[Dict]:
        """Suggest components based on directory structure."""
        components = []

        # Top-level directories often represent components
        for item in self.root_path.iterdir():
            if item.is_dir() and item.name not in self.IGNORE_DIRS and not item.name.startswith('.'):
                # Count files in directory
                file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                if file_count > 0:
                    components.append({
                        'id': f'comp_{item.name}',
                        'label': item.name.replace('_', ' ').title(),
                        'type': 'node',
                        'summary': f'Contains {file_count} files',
                        'files': [{'name': item.name, 'type': 'folder'}]
                    })

        return components
```

## Exit Criteria

All must pass before this sub-task is complete:

- [ ] Scanner correctly traverses directory structure
- [ ] Ignores common non-source directories (node_modules, __pycache__)
- [ ] Detects Python projects (requirements.txt, .py files)
- [ ] Detects JavaScript projects (package.json, .js/.ts files)
- [ ] Extracts dependencies from requirements.txt
- [ ] Extracts dependencies from package.json
- [ ] Finds entry points for Python projects
- [ ] Finds entry points for JavaScript projects
- [ ] Generates component suggestions from directory structure
- [ ] Output format compatible with Architect agent input
- [ ] Handles large codebases (1000+ files) without performance issues

## Tests Required

### test_codebase_scanner.py

```python
import pytest
from pathlib import Path
from analyzers.scanner import CodebaseScanner, AnalysisResult

class TestCodebaseScanner:
    @pytest.fixture
    def python_project(self, tmp_path):
        """Create a mock Python project."""
        (tmp_path / 'main.py').write_text('print("hello")')
        (tmp_path / 'requirements.txt').write_text('requests>=2.0\nflask==2.0.0')
        (tmp_path / 'src').mkdir()
        (tmp_path / 'src' / 'app.py').write_text('# app code')
        (tmp_path / 'src' / 'utils.py').write_text('# utils')
        (tmp_path / '__pycache__').mkdir()  # Should be ignored
        return tmp_path

    @pytest.fixture
    def js_project(self, tmp_path):
        """Create a mock JavaScript project."""
        (tmp_path / 'package.json').write_text('{"main": "index.js", "dependencies": {"express": "4.0"}}')
        (tmp_path / 'index.js').write_text('const x = 1')
        (tmp_path / 'node_modules').mkdir()  # Should be ignored
        return tmp_path

    def test_scan_python_project(self, python_project):
        """Scans Python project correctly."""
        scanner = CodebaseScanner(str(python_project))
        result = scanner.scan()

        assert 'Python' in result.languages
        assert result.file_count >= 3
        assert 'requests' in result.dependencies
        assert any('main.py' in ep for ep in result.entry_points)

    def test_scan_js_project(self, js_project):
        """Scans JavaScript project correctly."""
        scanner = CodebaseScanner(str(js_project))
        result = scanner.scan()

        assert 'JavaScript' in result.languages
        assert 'express' in result.dependencies

    def test_ignores_node_modules(self, js_project):
        """Does not scan node_modules."""
        (js_project / 'node_modules' / 'pkg').mkdir(parents=True)
        (js_project / 'node_modules' / 'pkg' / 'index.js').write_text('x')

        scanner = CodebaseScanner(str(js_project))
        result = scanner.scan()

        # Should only find root index.js
        assert result.file_count == 1

    def test_suggests_components(self, python_project):
        """Generates component suggestions."""
        scanner = CodebaseScanner(str(python_project))
        result = scanner.scan()

        assert len(result.components) >= 1
        assert any(c['label'] == 'Src' for c in result.components)
```

---

*Status: Pending*
*Estimated Complexity: High*
*Dependencies: None (standalone utility)*
