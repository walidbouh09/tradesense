# TradeSense AI Test Suite

Comprehensive testing suite for the TradeSense AI prop trading platform.

## Test Structure

```
tests/
├── __init__.py                 # Test suite configuration
├── unit/                       # Unit tests
│   ├── test_payments.py        # Payment service tests
│   ├── test_analytics.py       # Analytics service tests
│   └── test_*.py              # Other unit tests
├── integration/                # Integration tests
│   ├── test_api_integration.py # API endpoint tests
│   └── test_*.py              # Other integration tests
├── performance/                # Performance tests
├── security/                   # Security tests
└── conftest.py                # Shared test fixtures
```

## Running Tests

### All Tests
```bash
pytest
```

### With Coverage
```bash
pytest --cov=app --cov-report=html
```

### Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# API tests only
pytest -m api

# Performance tests
pytest -m performance
```

### Specific Test Files
```bash
# Run specific test file
pytest tests/unit/test_payments.py

# Run specific test class
pytest tests/unit/test_payments.py::TestPaymentService

# Run specific test method
pytest tests/unit/test_payments.py::TestPaymentService::test_create_payment_intent_success
```

## Test Coverage Requirements

- **Minimum Coverage**: 80%
- **Target Coverage**: 90%+
- **Critical Paths**: 95%+ (payments, trading logic, security)

## Test Types

### Unit Tests (`tests/unit/`)
- Test individual functions and methods
- Mock external dependencies
- Fast execution (< 100ms per test)
- No database or network calls

### Integration Tests (`tests/integration/`)
- Test API endpoints with real database
- Test component interactions
- Include external service mocking where needed
- Medium execution time

### Performance Tests (`tests/performance/`)
- Load testing for API endpoints
- Database query performance
- Memory usage monitoring
- Response time validation

### Security Tests (`tests/security/`)
- Authentication and authorization
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- Rate limiting verification

## Test Data

### Mock Data Strategy
- Use `pytest.fixture` for reusable test data
- Create realistic but deterministic data
- Avoid production data in tests
- Use factories for complex object creation

### Database Testing
- Use separate test database
- Clean up data between tests
- Use transactions for test isolation
- Mock external API calls

## Continuous Integration

Tests run automatically on:
- GitHub Actions (push/PR)
- Pre-commit hooks (local)
- Docker build process

### CI Pipeline
1. **Linting**: Black, flake8, mypy
2. **Unit Tests**: Fast feedback
3. **Integration Tests**: With test database
4. **Security Tests**: SAST/DAST scans
5. **Performance Tests**: Load testing

## Writing New Tests

### Unit Test Template
```python
import pytest
from app.service import ServiceClass

class TestServiceClass:
    """Test cases for ServiceClass."""

    @pytest.fixture
    def service_instance(self):
        """Create service instance for testing."""
        return ServiceClass()

    def test_method_success(self, service_instance):
        """Test successful method execution."""
        result = service_instance.method_name("input")
        assert result == "expected_output"

    def test_method_error_handling(self, service_instance):
        """Test error handling in method."""
        with pytest.raises(ValueError):
            service_instance.method_name("invalid_input")
```

### Integration Test Template
```python
import pytest
import json

class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_endpoint_success(self, client, auth_headers):
        """Test successful API endpoint call."""
        response = client.get('/api/endpoint', headers=auth_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'expected_field' in data
```

## Test Fixtures

### Shared Fixtures (`tests/conftest.py`)
- `app`: Flask test application
- `client`: Test client
- `auth_headers`: JWT authentication headers
- `db_session`: Database session for integration tests
- `mock_user`: Mock user data
- `mock_challenge`: Mock challenge data

### Custom Fixtures
Create fixtures for complex test data:
```python
@pytest.fixture
def complex_test_data():
    """Create complex test data structure."""
    return {
        'users': [...],
        'challenges': [...],
        'trades': [...]
    }
```

## Mocking Strategy

### External Services
```python
@patch('app.external_service.ExternalAPI.call')
def test_with_mocked_external_service(mock_call):
    mock_call.return_value = {'status': 'success'}
    # Test implementation
```

### Database Calls
```python
@patch('app.service.ServiceClass._db_query')
def test_with_mocked_database(mock_query):
    mock_query.return_value = mock_data
    # Test implementation
```

## Performance Testing

### API Response Times
```python
def test_api_response_time(client):
    import time

    start = time.time()
    response = client.get('/api/endpoint')
    duration = time.time() - start

    assert duration < 0.5  # 500ms max
    assert response.status_code == 200
```

### Load Testing
Use `locust` or `pytest-benchmark` for load testing:
```python
@pytest.mark.performance
def test_high_load_scenario(client):
    # Simulate multiple concurrent requests
    pass
```

## Security Testing

### Authentication Tests
```python
def test_unauthorized_access(client):
    response = client.get('/api/protected-endpoint')
    assert response.status_code in [401, 422]

def test_invalid_token(client):
    headers = {'Authorization': 'Bearer invalid_token'}
    response = client.get('/api/protected-endpoint', headers=headers)
    assert response.status_code == 401
```

### Input Validation
```python
def test_sql_injection_protection(client):
    malicious_input = "'; DROP TABLE users; --"
    response = client.post('/api/search', json={'query': malicious_input})
    assert response.status_code == 400
```

## Debugging Failed Tests

### Common Issues
1. **Database state**: Ensure proper cleanup between tests
2. **Mock objects**: Verify mock return values
3. **Async operations**: Use appropriate async test patterns
4. **External dependencies**: Mock all external API calls

### Debug Commands
```bash
# Run with detailed output
pytest -v -s

# Run single failing test
pytest tests/unit/test_example.py::TestClass::test_method -xvs

# Debug with pdb
pytest --pdb

# Show coverage for specific file
pytest --cov=app.service --cov-report=term-missing
```

## Test Maintenance

### Regular Tasks
- Update test data when schema changes
- Review and update mocked responses
- Monitor test execution time
- Update dependencies and test framework

### Code Review Checklist
- [ ] Tests cover all public methods
- [ ] Edge cases are tested
- [ ] Error conditions are handled
- [ ] Tests are independent and isolated
- [ ] Test names are descriptive
- [ ] Fixtures are reusable
- [ ] Mock objects are properly configured

## Contributing

1. Write tests for new features
2. Update tests when refactoring code
3. Maintain test coverage above 80%
4. Follow existing test patterns
5. Add documentation for complex test scenarios

## Troubleshooting

### Import Errors
- Ensure proper Python path configuration
- Check for circular imports in test files
- Verify all dependencies are installed

### Database Connection Issues
- Check test database configuration
- Ensure database is running and accessible
- Verify connection pooling settings

### Slow Tests
- Profile test execution time
- Optimize database queries
- Use appropriate fixtures and mocking
- Consider moving to integration test suite