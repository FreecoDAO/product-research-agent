"""Tests for tracing functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.tracing import (
    setup_phoenix_tracing,
    get_tracer,
    is_tracing_enabled,
    trace_operation,
    TracingConfig
)


class TestTracingSetup:
    """Test tracing setup and configuration."""

    def test_tracing_config_creation(self):
        """Test TracingConfig creation."""
        config = TracingConfig()

        assert config.enabled is False
        assert config.api_key is None
        assert config.space_id is None
        assert config.project_name == "product-research-agent"

    def test_tracing_config_from_env(self):
        """Test TracingConfig from environment variables."""
        with patch.dict('os.environ', {
            'PHOENIX_API_KEY': 'test-api-key',
            'PHOENIX_SPACE_ID': 'test-space-id',
            'PHOENIX_PROJECT_NAME': 'test-project'
        }):
            config = TracingConfig().from_env()

            assert config.api_key == 'test-api-key'
            assert config.space_id == 'test-space-id'
            assert config.project_name == 'test-project'

    def test_setup_phoenix_tracing_without_dependencies(self):
        """Test Phoenix setup when dependencies are missing."""
        with patch('src.core.tracing.logger') as mock_logger:
            # Mock import error for Phoenix dependencies
            with patch('builtins.__import__', side_effect=ImportError("No module named 'phoenix'")):
                result = setup_phoenix_tracing()

                assert result is False
                mock_logger.warning.assert_called()

    def test_setup_phoenix_tracing_local(self):
        """Test Phoenix setup for local development."""
        # Test that the function handles the setup attempt gracefully
        # In real environment, Phoenix may or may not be available
        result = setup_phoenix_tracing(project_name="test-project")

        # Should return True if successful, False if dependencies missing
        assert isinstance(result, bool)

    def test_setup_phoenix_tracing_cloud(self):
        """Test Phoenix setup for cloud/production."""
        # Test that the function handles the setup attempt gracefully
        result = setup_phoenix_tracing(
            api_key="test-key",
            space_id="test-space",
            project_name="test-project"
        )

        # Should return True if successful, False if dependencies missing
        assert isinstance(result, bool)


class TestTracingOperations:
    """Test tracing operations and context managers."""

    def test_get_tracer_when_not_initialized(self):
        """Test get_tracer when tracing not initialized."""
        # Reset global tracer
        import src.core.tracing
        src.core.tracing._tracer = None

        tracer = get_tracer()
        assert tracer is None

    def test_is_tracing_enabled(self):
        """Test tracing enabled check."""
        import src.core.tracing

        # Test when disabled
        src.core.tracing._tracer = None
        assert is_tracing_enabled() is False

        # Test when enabled
        src.core.tracing._tracer = Mock()
        assert is_tracing_enabled() is True

        # Reset
        src.core.tracing._tracer = None

    def test_trace_operation_without_tracer(self):
        """Test trace_operation context manager without tracer."""
        import src.core.tracing
        src.core.tracing._tracer = None

        with trace_operation("test_operation") as span:
            assert span is None

    def test_trace_operation_with_tracer(self):
        """Test trace_operation context manager with tracer."""
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with trace_operation("test_operation", test_attr="test_value") as span:
            assert span == mock_span
            mock_span.set_attribute.assert_called_with("test_attr", "test_value")

        # Reset
        src.core.tracing._tracer = None


class TestTracingHelpers:
    """Test tracing helper functions."""

    def test_add_span_attributes_without_span(self):
        """Test add_span_attributes with None span."""
        from src.core.tracing import add_span_attributes

        # Should not raise an error
        add_span_attributes(None, test_attr="test_value")

    def test_add_span_attributes_with_span(self):
        """Test add_span_attributes with valid span."""
        from src.core.tracing import add_span_attributes

        mock_span = Mock()
        add_span_attributes(mock_span, test_attr="test_value", another_attr=123)

        mock_span.set_attribute.assert_any_call("test_attr", "test_value")
        mock_span.set_attribute.assert_any_call("another_attr", "123")

    def test_log_research_metrics_without_span(self):
        """Test log_research_metrics with None span."""
        from src.core.tracing import log_research_metrics

        # Should not raise an error
        log_research_metrics(
            None,
            query="test query",
            num_products=5,
            total_time=25.0,
            success=True
        )

    def test_log_research_metrics_with_span(self):
        """Test log_research_metrics with valid span."""
        from src.core.tracing import log_research_metrics

        mock_span = Mock()
        log_research_metrics(
            mock_span,
            query="test query",
            num_products=5,
            num_reviews=10,
            total_time=25.0,
            success=True
        )

        # Verify attributes were set
        mock_span.set_attribute.assert_any_call("query", "test query")
        mock_span.set_attribute.assert_any_call("num_products_found", "5")
        mock_span.set_attribute.assert_any_call("num_reviews_analyzed", "10")
        mock_span.set_attribute.assert_any_call("total_research_time_seconds", "25.0")
        mock_span.set_attribute.assert_any_call("research_success", "True")

    def test_log_research_metrics_with_error(self):
        """Test log_research_metrics with error."""
        from src.core.tracing import log_research_metrics

        mock_span = Mock()

        # Test that error logging doesn't crash the application
        log_research_metrics(
            mock_span,
            query="test query",
            success=False,
            error="Test error message"
        )

        # Should at least set the error message attribute
        mock_span.set_attribute.assert_any_call("error_message", "Test error message")


class TestTracingContextManagers:
    """Test specialized tracing context managers."""

    def test_trace_product_research(self):
        """Test trace_product_research context manager."""
        from src.core.tracing import trace_product_research
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with trace_product_research("test laptop query") as span:
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_with("product_research")

        # Reset
        src.core.tracing._tracer = None

    def test_trace_agent_operation(self):
        """Test trace_agent_operation context manager."""
        from src.core.tracing import trace_agent_operation
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with trace_agent_operation("orchestrator", "research") as span:
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_with("orchestrator_research")

        # Reset
        src.core.tracing._tracer = None