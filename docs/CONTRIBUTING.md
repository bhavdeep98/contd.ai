# Contributing to Contd.ai

We welcome contributions! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10+
- PostgreSQL (for integration tests)
- Git

### Clone and Install

```bash
git clone https://github.com/contd/contd.ai.git
cd contd.ai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install with dev dependencies
pip install -e ".[dev]"
pip install -r requirements-test.txt
```

### Run Tests

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_sdk.py

# With coverage
pytest --cov=contd tests/
```

## Code Style

We use:
- **Black** for formatting
- **isort** for import sorting
- **mypy** for type checking
- **ruff** for linting

```bash
# Format code
black contd/ tests/
isort contd/ tests/

# Type check
mypy contd/

# Lint
ruff check contd/
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

## Project Structure

```
contd/
├── api/           # REST & gRPC endpoints
├── cli/           # Command-line interface
├── core/          # Execution engine
├── models/        # Data models
├── observability/ # Metrics & tracing
├── persistence/   # Storage adapters
├── runtime/       # Execution runtime
└── sdk/           # User-facing decorators

sdks/
├── typescript/    # TypeScript SDK
├── go/            # Go SDK
└── java/          # Java SDK

tests/             # Test suite
docs/              # Documentation
examples/          # Example workflows
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clear, documented code
- Add tests for new functionality
- Update documentation if needed

### 3. Test Your Changes

```bash
# Run tests
pytest tests/

# Check types
mypy contd/

# Format
black contd/ tests/
```

### 4. Commit

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat: add savepoint metadata validation"
git commit -m "fix: handle lease expiration during heartbeat"
git commit -m "docs: update API reference for webhooks"
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

### 5. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

## Pull Request Guidelines

### PR Checklist

- [ ] Tests pass (`pytest tests/`)
- [ ] Types check (`mypy contd/`)
- [ ] Code formatted (`black`, `isort`)
- [ ] Documentation updated (if applicable)
- [ ] Changelog entry added (for features/fixes)

### PR Description Template

```markdown
## Summary
Brief description of changes.

## Changes
- Added X
- Fixed Y
- Updated Z

## Testing
How was this tested?

## Related Issues
Fixes #123
```

## Testing Guidelines

### Unit Tests

```python
# tests/test_my_feature.py
import pytest
from contd.sdk import workflow, step

def test_step_returns_result():
    @step()
    def my_step():
        return {"value": 42}
    
    # Use test harness
    from contd.sdk.testing import ContdTestCase
    tc = ContdTestCase()
    tc.setUp()
    
    @workflow()
    def test_workflow():
        return my_step()
    
    result = tc.run_workflow("test", test_workflow, {})
    assert result["value"] == 42
    tc.tearDown()
```

### Integration Tests

```python
# tests/test_integration.py
import pytest

@pytest.fixture
def engine():
    from contd.core.engine import ExecutionEngine
    engine = ExecutionEngine.get_instance()
    yield engine
    engine.reset()

def test_workflow_recovery(engine):
    # Test full recovery flow
    ...
```

### Mocking External Services

```python
from unittest.mock import patch, MagicMock

def test_with_mock_api():
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"data": []}
        result = fetch_data("http://api.example.com")
        assert result["data"] == []
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int = 10) -> dict:
    """Short description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.
    
    Returns:
        Description of return value.
    
    Raises:
        ValueError: When param1 is empty.
    
    Example:
        >>> my_function("test", 20)
        {"result": "test-20"}
    """
```

### Updating Docs

Documentation lives in `docs/`:
- `ARCHITECTURE.md` - System design
- `API_REFERENCE.md` - API documentation
- `QUICKSTART.md` - Getting started
- `TROUBLESHOOTING.md` - Common issues

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release PR
4. After merge, tag release:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
5. GitHub Actions publishes to PyPI

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/contd/contd.ai/discussions)
- **Bugs**: Open an [Issue](https://github.com/contd/contd.ai/issues)
- **Chat**: Join [Discord](https://discord.gg/contd)

## Code of Conduct

Be respectful and inclusive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
