# Release Management Guide

This document explains how to manage releases for the ECHR Extractor package using automated versioning.

## 🚀 Automated Versioning with setuptools_scm

The package now uses **setuptools_scm** for automatic version management based on Git tags. This eliminates the need to manually update version numbers in multiple files.

### How It Works

1. **Version Source**: Versions are automatically generated from Git tags
2. **Tag Format**: Use semantic versioning tags like `v1.0.45`, `v1.1.0`, `v2.0.0`
3. **Automatic Generation**: The version is generated at build time from the latest Git tag
4. **Development Versions**: Uncommitted changes get a `.dev` suffix

### Version Examples

- **Release Tag**: `v1.0.45` → Version: `1.0.45`
- **Development**: `v1.0.45` + uncommitted changes → Version: `1.0.46.dev0+gfc123e3.d20251008`
- **Pre-release**: `v1.0.45` + 2 commits → Version: `1.0.46.dev2+gfc123e3`

## 📋 Release Process

### Option 1: Using the Release Script (Recommended)

```bash
# Patch release (1.0.45 → 1.0.46)
python scripts/release.py patch

# Minor release (1.0.45 → 1.1.0)
python scripts/release.py minor

# Major release (1.0.45 → 2.0.0)
python scripts/release.py major

# Specific version
python scripts/release.py 1.2.3
```

### Option 2: Manual Git Commands

```bash
# 1. Ensure working directory is clean
git status

# 2. Create and push a tag
git tag -a v1.0.46 -m "Release 1.0.46"
git push origin v1.0.46

# 3. GitHub Actions will automatically:
#    - Build the package
#    - Upload to PyPI
#    - Create a GitHub release
```

## 🔄 GitHub Actions Integration

The CI/CD pipeline automatically:

1. **Detects new tags** on the main branch
2. **Builds the package** with the correct version
3. **Uploads to PyPI** with the tag version
4. **Creates GitHub releases** with the same version
5. **Signs packages** with Sigstore for security

### Workflow Triggers

- **Pull Requests**: Run tests, linting, and build verification
- **Main Branch Push**: Run tests, linting, and build verification (no PyPI release)
- **Tag Push**: Full release pipeline (build, test, upload to PyPI, create release)

### CI/CD Behavior

- **Development**: All jobs run on PRs and main branch pushes for testing
- **Release**: Only tagged commits trigger PyPI publishing and GitHub releases
- **Artifacts**: Build artifacts are only uploaded for tagged releases
- **Version Display**: Shows the version that would be built for debugging

## 📦 Package Version Access

### In Python Code

```python
# The version is automatically available in your package
from echr_extractor import __version__
print(__version__)  # e.g., "1.0.45"

# Or using setuptools_scm directly
import setuptools_scm
version = setuptools_scm.get_version()
```

### In CLI

```bash
# Check current version
python -c "import setuptools_scm; print(setuptools_scm.get_version())"

# Check what version would be built
python -c "import setuptools_scm; print(setuptools_scm.get_version(write_to='version.py'))"
```

## 🏷️ Semantic Versioning Guidelines

Follow [Semantic Versioning](https://semver.org/) principles:

- **MAJOR** (2.0.0): Breaking changes, incompatible API changes
- **MINOR** (1.1.0): New features, backward compatible
- **PATCH** (1.0.1): Bug fixes, backward compatible

### Examples

- **Bug Fix**: `1.0.45` → `1.0.46` (patch)
- **New Feature**: `1.0.45` → `1.1.0` (minor)
- **Breaking Change**: `1.0.45` → `2.0.0` (major)

## 🔧 Configuration Files

### pyproject.toml
```toml
[project]
name = "echr-extractor"
dynamic = ["version"]  # Version is now dynamic

[tool.setuptools_scm]
write_to = "src/echr_extractor/_version.py"  # Auto-generate version file
```

### GitHub Actions (.github/workflows/ci.yml)
- Automatically detects version from Git tags
- No more hardcoded version numbers
- Dynamic release naming

## 🚨 Important Notes

1. **Always tag from main branch**: Tags should be created from the main branch
2. **Clean working directory**: Ensure no uncommitted changes before tagging
3. **Test before release**: Run tests locally before creating a release tag
4. **Changelog**: Consider maintaining a CHANGELOG.md for release notes

## 🐛 Troubleshooting

### Version not updating?
- Ensure you're on the main branch
- Check that the tag was pushed: `git push origin v1.0.46`
- Verify GitHub Actions ran successfully

### Development version showing?
- This is normal for uncommitted changes
- Create a proper release tag for stable versions

### Build failures?
- Check that setuptools_scm is installed: `pip install setuptools_scm`
- Verify pyproject.toml configuration is correct

### "Local versions not allowed" error on PyPI?
- **Cause**: setuptools_scm was generating versions with local identifiers (e.g., `1.0.47+abc123`)
- **Solution**: The configuration now uses `local_scheme = "no-local-version"` to prevent this
- **Prevention**: Only build from clean, tagged commits (GitHub Actions now only runs on tags)
- **Manual fix**: Ensure working directory is clean before creating tags

## 📚 Additional Resources

- [setuptools_scm Documentation](https://github.com/pypa/setuptools_scm)
- [Semantic Versioning](https://semver.org/)
- [Python Packaging User Guide](https://packaging.python.org/)
