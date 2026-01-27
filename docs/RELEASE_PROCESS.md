# Release Process

## Overview

Contd follows semantic versioning (SemVer) and uses automated release workflows.

## Version Numbers

- **MAJOR** (1.x.x): Breaking API changes
- **MINOR** (x.1.x): New features, backward compatible
- **PATCH** (x.x.1): Bug fixes, backward compatible

## Release Checklist

### Pre-Release

1. **Update Version**
   ```bash
   # Update version in pyproject.toml
   # Update version in contd/__init__.py
   # Update version in helm/contd/Chart.yaml
   ```

2. **Update Changelog**
   - Move [Unreleased] items to new version section
   - Add release date
   - Review all entries for accuracy

3. **Run Tests**
   ```bash
   pytest tests/ -v
   python -m benchmarks.run_benchmarks
   ```

4. **Update Documentation**
   - Review API documentation
   - Update migration guides if needed
   - Check all examples work

### Creating a Release

1. **Create Release Branch** (for major/minor)
   ```bash
   git checkout -b release/v1.2.0
   ```

2. **Final Review**
   - All tests pass
   - Documentation updated
   - Changelog complete

3. **Tag the Release**
   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```

4. **GitHub Actions Automation**
   - Builds Docker images (multi-arch)
   - Publishes to PyPI
   - Creates GitHub Release
   - Publishes Helm chart

### Post-Release

1. **Verify Artifacts**
   - Check PyPI package
   - Check Docker images
   - Check Helm chart

2. **Announce**
   - Discord announcement
   - Twitter/social media
   - Update website

3. **Monitor**
   - Watch for issues
   - Monitor error rates
   - Check community feedback

## Hotfix Process

For critical bugs in production:

1. Branch from release tag
   ```bash
   git checkout -b hotfix/v1.2.1 v1.2.0
   ```

2. Fix and test

3. Tag and release
   ```bash
   git tag -a v1.2.1 -m "Hotfix v1.2.1"
   ```

4. Merge back to main

## Release Schedule

- **Patch releases**: As needed for bug fixes
- **Minor releases**: Monthly (feature releases)
- **Major releases**: Annually or as needed

## Rollback Procedure

If a release has critical issues:

1. Revert the release tag
2. Publish previous version
3. Communicate to users
4. Fix and re-release
