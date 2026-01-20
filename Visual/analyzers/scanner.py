"""
Codebase Scanner - File system analysis for existing projects.
Detects languages, dependencies, entry points, and suggests components.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class FileInfo:
    """Information about a source file."""
    path: str
    name: str
    extension: str
    size: int
    lines: int = 0


@dataclass
class AnalysisResult:
    """Result of codebase analysis."""
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
        """Convert to dictionary for JSON serialization."""
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
    """Scans and analyzes codebases to extract structure and dependencies."""

    IGNORE_DIRS = {
        'node_modules', '__pycache__', '.git', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.next', '.nuxt',
        'coverage', '.pytest_cache', '.mypy_cache', '.tox',
        'eggs', '.eggs', '*.egg-info', 'htmlcov', '.hypothesis',
        '.ruff_cache', '.cache', 'target', 'out', 'bin', 'obj'
    }

    IGNORE_FILES = {
        '.DS_Store', 'Thumbs.db', '.gitignore', '.env', '.env.local',
        'package-lock.json', 'yarn.lock', 'poetry.lock', 'pnpm-lock.yaml',
        'Pipfile.lock', 'Cargo.lock', 'composer.lock'
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
        '.h': 'C/C++',
        '.hpp': 'C++',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.scala': 'Scala',
        '.vue': 'Vue',
        '.svelte': 'Svelte',
        '.sql': 'SQL',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.sass': 'Sass',
        '.less': 'Less'
    }

    def __init__(self, root_path: str):
        """
        Initialize the scanner.

        Args:
            root_path: Path to the codebase root directory

        Raises:
            ValueError: If path does not exist
        """
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")
        if not self.root_path.is_dir():
            raise ValueError(f"Path is not a directory: {root_path}")

    def scan(self) -> AnalysisResult:
        """
        Perform full codebase analysis.

        Returns:
            AnalysisResult with detected languages, dependencies, etc.
        """
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
        if 'Go' in result.languages:
            result.entry_points.extend(self._find_go_entry_points())
        if 'Rust' in result.languages:
            result.dependencies.extend(self._extract_rust_deps())
            result.entry_points.extend(self._find_rust_entry_points())

        # Remove duplicates
        result.dependencies = list(dict.fromkeys(result.dependencies))
        result.entry_points = list(dict.fromkeys(result.entry_points))

        # Generate component suggestions
        result.components = self._suggest_components(result)

        return result

    def _scan_files(self) -> List[FileInfo]:
        """Scan all source files in the codebase."""
        files = []

        for root, dirs, filenames in os.walk(self.root_path):
            # Filter ignored directories (in-place to affect os.walk)
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith('.')]

            for filename in filenames:
                if filename in self.IGNORE_FILES or filename.startswith('.'):
                    continue

                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                if ext in self.LANGUAGE_EXTENSIONS:
                    try:
                        lines = sum(1 for _ in open(filepath, 'r', errors='ignore'))
                    except Exception:
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
        """Detect primary languages used based on file extensions."""
        ext_counts = Counter(f.extension for f in files)

        languages = []
        for ext, count in ext_counts.most_common():
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                if lang not in languages:
                    languages.append(lang)

        return languages

    def _build_structure(self) -> Dict:
        """Build directory tree structure (limited depth)."""
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
        """Recursively build directory structure with depth limit."""
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
            try:
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('-'):
                            # Extract package name (before version specifiers)
                            pkg = line.split('==')[0].split('>=')[0].split('<=')[0]
                            pkg = pkg.split('<')[0].split('>')[0].split('[')[0].split(';')[0]
                            if pkg:
                                deps.append(pkg.strip())
            except Exception:
                pass

        # Check setup.py for install_requires (simplified)
        setup_file = self.root_path / 'setup.py'
        if setup_file.exists():
            try:
                content = setup_file.read_text()
                if 'install_requires' in content:
                    # Very basic extraction - just note that deps exist
                    pass
            except Exception:
                pass

        return deps

    def _extract_js_deps(self) -> List[str]:
        """Extract JavaScript/TypeScript dependencies from package.json."""
        deps = []

        pkg_file = self.root_path / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file, 'r') as f:
                    pkg = json.load(f)
                deps.extend(pkg.get('dependencies', {}).keys())
                # Optionally include devDependencies for tooling context
                # deps.extend(pkg.get('devDependencies', {}).keys())
            except (json.JSONDecodeError, Exception):
                pass

        return deps

    def _extract_rust_deps(self) -> List[str]:
        """Extract Rust dependencies from Cargo.toml."""
        deps = []

        cargo_file = self.root_path / 'Cargo.toml'
        if cargo_file.exists():
            try:
                content = cargo_file.read_text()
                in_deps = False
                for line in content.split('\n'):
                    if line.strip() == '[dependencies]':
                        in_deps = True
                        continue
                    if line.startswith('[') and in_deps:
                        break
                    if in_deps and '=' in line:
                        pkg = line.split('=')[0].strip()
                        if pkg and not pkg.startswith('#'):
                            deps.append(pkg)
            except Exception:
                pass

        return deps

    def _find_python_entry_points(self) -> List[str]:
        """Find Python entry points (main.py, __main__.py, etc.)."""
        entry_points = []
        patterns = ['main.py', 'app.py', '__main__.py', 'cli.py', 'run.py', 'server.py']

        for pattern in patterns:
            matches = list(self.root_path.rglob(pattern))
            for match in matches[:3]:  # Limit to 3 per pattern
                rel_path = str(match.relative_to(self.root_path))
                if '__pycache__' not in rel_path and 'test' not in rel_path.lower():
                    entry_points.append(rel_path)

        return entry_points

    def _find_js_entry_points(self) -> List[str]:
        """Find JavaScript/TypeScript entry points."""
        entry_points = []

        # Check package.json main field
        pkg_file = self.root_path / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file, 'r') as f:
                    pkg = json.load(f)
                if 'main' in pkg:
                    entry_points.append(pkg['main'])
                if 'module' in pkg:
                    entry_points.append(pkg['module'])
            except Exception:
                pass

        # Common patterns
        patterns = ['index.js', 'index.ts', 'app.js', 'app.ts', 'server.js', 'main.js', 'main.ts']
        for pattern in patterns:
            # Check in root and src
            for check_path in [self.root_path, self.root_path / 'src']:
                if check_path.exists():
                    match = check_path / pattern
                    if match.exists():
                        entry_points.append(str(match.relative_to(self.root_path)))

        return entry_points

    def _find_go_entry_points(self) -> List[str]:
        """Find Go entry points (main.go files in cmd/ or root)."""
        entry_points = []

        # Check cmd directory
        cmd_dir = self.root_path / 'cmd'
        if cmd_dir.exists():
            for main_file in cmd_dir.rglob('main.go'):
                entry_points.append(str(main_file.relative_to(self.root_path)))

        # Check root
        root_main = self.root_path / 'main.go'
        if root_main.exists():
            entry_points.append('main.go')

        return entry_points

    def _find_rust_entry_points(self) -> List[str]:
        """Find Rust entry points (main.rs, lib.rs)."""
        entry_points = []

        for pattern in ['src/main.rs', 'src/lib.rs', 'main.rs']:
            check_path = self.root_path / pattern
            if check_path.exists():
                entry_points.append(pattern)

        return entry_points

    def _suggest_components(self, result: AnalysisResult) -> List[Dict]:
        """Suggest components based on directory structure and patterns."""
        components = []

        # Top-level directories often represent components/modules
        for item in self.root_path.iterdir():
            if item.is_dir() and item.name not in self.IGNORE_DIRS and not item.name.startswith('.'):
                # Count source files in directory
                source_files = []
                for ext in self.LANGUAGE_EXTENSIONS:
                    source_files.extend(item.rglob(f'*{ext}'))

                file_count = len(source_files)
                if file_count > 0:
                    # Determine component type based on common patterns
                    comp_type = 'module'
                    name_lower = item.name.lower()
                    if name_lower in ('api', 'routes', 'endpoints', 'handlers'):
                        comp_type = 'api'
                    elif name_lower in ('models', 'entities', 'schemas'):
                        comp_type = 'data'
                    elif name_lower in ('services', 'core', 'business'):
                        comp_type = 'service'
                    elif name_lower in ('utils', 'helpers', 'lib', 'common'):
                        comp_type = 'utility'
                    elif name_lower in ('tests', 'test', 'spec', '__tests__'):
                        comp_type = 'test'
                    elif name_lower in ('ui', 'views', 'components', 'pages'):
                        comp_type = 'ui'
                    elif name_lower in ('db', 'database', 'migrations'):
                        comp_type = 'database'

                    components.append({
                        'id': f'comp_{item.name}',
                        'label': item.name.replace('_', ' ').replace('-', ' ').title(),
                        'type': 'node',
                        'category': comp_type,
                        'summary': f'Contains {file_count} source files',
                        'files': [{'name': item.name, 'type': 'folder'}],
                        'file_count': file_count
                    })

        # Sort by file count (larger components first)
        components.sort(key=lambda x: x.get('file_count', 0), reverse=True)

        return components

    def quick_scan(self) -> Dict[str, Any]:
        """
        Perform a quick scan returning just summary info.
        Useful for large codebases where full scan is too slow.
        """
        # Just count files by extension
        ext_counts = Counter()
        file_count = 0

        for root, dirs, filenames in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in self.LANGUAGE_EXTENSIONS:
                    ext_counts[ext] += 1
                    file_count += 1

        languages = []
        for ext, count in ext_counts.most_common():
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                if lang not in languages:
                    languages.append(lang)

        return {
            'root_path': str(self.root_path),
            'file_count': file_count,
            'languages': languages,
            'extension_counts': dict(ext_counts)
        }
