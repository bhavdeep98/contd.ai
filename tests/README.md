# Contd.ai Test Suite

## Quick Start

### Install Dependencies
```bash
pip install -r requirements-test.txt
```

### Run All Tests
```bash
python run_tests.py
```

Or directly with pytest:
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=contd --cov-report=html --cov-report=term-missing
```

View HTML report: `open htmlcov/index.html`

---

## Test Organization

```
tests/
├── test_metrics.py                    # Metrics collection tests
├── test_exporter.py                   # HTTP exporter tests
├── test_background.py                 # Background collector tests
└── test_observability_integration.py  # Integration tests
```

---

## Current Coverage

**Observability Module: 83%**

See `TEST_COVERAGE.md` for detailed coverage analysis.

---

## Running Specific Tests

### Single Test File
```bash
pytest tests/test_metrics.py -v
```

### Single Test Class
```bash
pytest tests/test_metrics.py::TestMetricsCollector -v
```

### Single Test Method
```bash
pytest tests/test_metrics.py::TestMetricsCollector::test_record_workflow_start -v
```

### Tests by Marker
```bash
pytest tests/ -m unit          # Unit tests only
pytest tests/ -m integration   # Integration tests only
pytest tests/ -m "not slow"    # Skip slow tests
```

---

## Test Output

### Verbose Mode
```bash
pytest tests/ -v
```

### Show Print Statements
```bash
pytest tests/ -s
```

### Stop on First Failure
```bash
pytest tests/ -x
```

### Run Last Failed Tests
```bash
pytest tests/ --lf
```

---

## Coverage Reports

### Terminal Report
```bash
pytest tests/ --cov=contd --cov-report=term-missing
```

### HTML Report
```bash
pytest tests/ --cov=contd --cov-report=html
open htmlcov/index.html
```

### JSON Report
```bash
pytest tests/ --cov=contd --cov-report=json
cat coverage.json
```

---

## Writing Tests

### Test Structure
```python
import pytest
from contd.observability import collector

class TestMyFeature:
    """Test my feature"""
    
    def setup_method(self):
        """Setup before each test"""
        pass
    
    def teardown_method(self):
        """Cleanup after each test"""
        pass
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        # Arrange
        workflow_name = "test"
        
        # Act
        collector.record_workflow_start(workflow_name, trigger="api")
        
        # Assert
        # Verify metric was recorded
```

### Using Fixtures
```python
@pytest.fixture
def metrics_server():
    """Start metrics server for testing"""
    from contd.observability import setup_observability, teardown_observability
    setup_observability(metrics_port=9999)
    yield
    teardown_observability()

def test_with_server(metrics_server):
    """Test that uses metrics server"""
    # Server is running
    pass
```

### Mocking
```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency"""
    with patch('contd.observability.metrics.collector') as mock_collector:
        mock_collector.record_workflow_start.return_value = None
        # Test code
```

---

## CI/CD Integration

### GitHub Actions
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/ --cov=contd --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Troubleshooting

### Port Already in Use
If tests fail with "Address already in use":
```bash
# Kill process on port 9090
lsof -ti:9090 | xargs kill -9
```

### Import Errors
Ensure contd package is in PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Slow Tests
Skip slow tests:
```bash
pytest tests/ -m "not slow"
```

---

## Next Steps

See `TEST_COVERAGE.md` for:
- Coverage analysis
- Untested modules
- Test roadmap
- Priority areas
