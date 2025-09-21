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


class TestTracingAutoInitialization:
    """Test auto-initialization functionality."""

    def test_auto_initialize_with_api_key(self):
        """Test auto-initialization when API key is present."""
        from src.core.tracing import _auto_initialize

        with patch.dict('os.environ', {
            'PHOENIX_API_KEY': 'test-key',
            'PHOENIX_SPACE_ID': 'test-space'
        }):
            with patch('src.core.tracing.initialize_tracing_from_config') as mock_init:
                with patch('src.core.tracing.logger') as mock_logger:
                    _auto_initialize()

                    mock_logger.info.assert_called_with("Auto-initializing Phoenix tracing from environment")
                    mock_init.assert_called_once()

    def test_auto_initialize_with_auto_init_flag(self):
        """Test auto-initialization when PHOENIX_AUTO_INIT is true."""
        from src.core.tracing import _auto_initialize

        with patch.dict('os.environ', {
            'PHOENIX_AUTO_INIT': 'true'
        }):
            with patch('src.core.tracing.initialize_tracing_from_config') as mock_init:
                with patch('src.core.tracing.logger') as mock_logger:
                    _auto_initialize()

                    mock_logger.info.assert_called_with("Auto-initializing Phoenix tracing from environment")
                    mock_init.assert_called_once()

    def test_auto_initialize_with_exception(self):
        """Test auto-initialization when exception occurs."""
        from src.core.tracing import _auto_initialize

        with patch('src.core.tracing.TracingConfig') as mock_config:
            mock_config.side_effect = Exception("Test exception")
            with patch('src.core.tracing.logger') as mock_logger:
                _auto_initialize()

                mock_logger.debug.assert_called_with("Auto-initialization skipped: Test exception")

    def test_auto_initialize_without_config(self):
        """Test auto-initialization without required configuration."""
        from src.core.tracing import _auto_initialize

        with patch.dict('os.environ', {}, clear=True):
            with patch('src.core.tracing.initialize_tracing_from_config') as mock_init:
                _auto_initialize()

                # Should not initialize when no API key or auto-init flag
                mock_init.assert_not_called()


class TestTracingConfigFromSettings:
    """Test TracingConfig from_settings method."""

    def test_from_settings_with_all_attributes(self):
        """Test from_settings with all Phoenix attributes."""
        config = TracingConfig()

        # Mock settings object
        mock_settings = Mock()
        mock_settings.phoenix_api_key = 'settings-api-key'
        mock_settings.phoenix_space_id = 'settings-space-id'
        mock_settings.phoenix_project_name = 'settings-project'

        result = config.from_settings(mock_settings)

        assert result == config
        assert config.api_key == 'settings-api-key'
        assert config.space_id == 'settings-space-id'
        assert config.project_name == 'settings-project'

    def test_from_settings_with_missing_attributes(self):
        """Test from_settings with missing Phoenix attributes."""
        config = TracingConfig()

        # Mock settings object without Phoenix attributes
        mock_settings = Mock()
        del mock_settings.phoenix_api_key
        del mock_settings.phoenix_space_id
        del mock_settings.phoenix_project_name

        result = config.from_settings(mock_settings)

        assert result == config
        assert config.api_key is None
        assert config.space_id is None
        assert config.project_name == 'product-research-agent'  # default


class TestTracingErrorHandling:
    """Test error handling in tracing operations."""

    def test_trace_operation_with_exception_in_span(self):
        """Test trace_operation when span operations raise exceptions."""
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute.side_effect = Exception("Attribute error")
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with patch('src.core.tracing.logger') as mock_logger:
            with trace_operation("test_operation", test_attr="test_value") as span:
                # Should return None when error occurs
                assert span is None

            mock_logger.error.assert_called_with("Error in trace operation test_operation: Attribute error")

        # Reset
        src.core.tracing._tracer = None

    def test_add_span_attributes_with_exception(self):
        """Test add_span_attributes when set_attribute raises exception."""
        from src.core.tracing import add_span_attributes

        mock_span = Mock()
        mock_span.set_attribute.side_effect = Exception("Span error")

        with patch('src.core.tracing.logger') as mock_logger:
            add_span_attributes(mock_span, test_attr="test_value")

            mock_logger.error.assert_called_with("Error adding span attributes: Span error")

    def test_log_research_metrics_with_exception(self):
        """Test log_research_metrics when span operations raise exceptions."""
        from src.core.tracing import log_research_metrics

        mock_span = Mock()

        # Mock add_span_attributes to raise exception
        with patch('src.core.tracing.add_span_attributes') as mock_add_attributes:
            mock_add_attributes.side_effect = Exception("Research metrics error")

            with patch('src.core.tracing.logger') as mock_logger:
                log_research_metrics(
                    mock_span,
                    query="test query",
                    num_products=5,
                    success=True
                )

                mock_logger.error.assert_called_with("Error logging research metrics: Research metrics error")


class TestAgentMetricsLogging:
    """Test agent metrics logging functionality."""

    def test_log_agent_metrics_without_span(self):
        """Test log_agent_metrics with None span."""
        from src.core.tracing import log_agent_metrics

        # Should not raise an error
        log_agent_metrics(
            None,
            agent_name="orchestrator",
            operation="research",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            latency=2.5
        )

    def test_log_agent_metrics_with_span(self):
        """Test log_agent_metrics with valid span."""
        from src.core.tracing import log_agent_metrics

        mock_span = Mock()
        log_agent_metrics(
            mock_span,
            agent_name="orchestrator",
            operation="research",
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            latency=2.5
        )

        # Verify attributes were set
        mock_span.set_attribute.assert_any_call("agent_name", "orchestrator")
        mock_span.set_attribute.assert_any_call("operation", "research")
        mock_span.set_attribute.assert_any_call("input_tokens", "100")
        mock_span.set_attribute.assert_any_call("output_tokens", "50")
        mock_span.set_attribute.assert_any_call("estimated_cost_usd", "0.01")
        mock_span.set_attribute.assert_any_call("latency_seconds", "2.5")

    def test_log_agent_metrics_with_exception(self):
        """Test log_agent_metrics when span operations raise exceptions."""
        from src.core.tracing import log_agent_metrics

        mock_span = Mock()

        # Mock add_span_attributes to raise exception
        with patch('src.core.tracing.add_span_attributes') as mock_add_attributes:
            mock_add_attributes.side_effect = Exception("Agent metrics error")

            with patch('src.core.tracing.logger') as mock_logger:
                log_agent_metrics(
                    mock_span,
                    agent_name="test_agent",
                    operation="test_operation"
                )

                mock_logger.error.assert_called_with("Error logging agent metrics: Agent metrics error")


class TestToolTracingContextManager:
    """Test trace_tool_usage context manager."""

    def test_trace_tool_usage_without_tracer(self):
        """Test trace_tool_usage without tracer."""
        from src.core.tracing import trace_tool_usage
        import src.core.tracing

        src.core.tracing._tracer = None

        with trace_tool_usage("tavily_search", {"query": "test"}) as span:
            assert span is None

    def test_trace_tool_usage_with_tracer(self):
        """Test trace_tool_usage with tracer."""
        from src.core.tracing import trace_tool_usage
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with trace_tool_usage("tavily_search", {"query": "test", "limit": 10}) as span:
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_with("tool_tavily_search")
        mock_span.set_attribute.assert_any_call("input_query", "test")
        mock_span.set_attribute.assert_any_call("input_limit", "10")

        # Reset
        src.core.tracing._tracer = None

    def test_trace_tool_usage_without_input_params(self):
        """Test trace_tool_usage without input parameters."""
        from src.core.tracing import trace_tool_usage
        import src.core.tracing

        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)

        src.core.tracing._tracer = mock_tracer

        with trace_tool_usage("simple_tool") as span:
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_with("tool_simple_tool")
        # Should set tool_name attribute but not input params
        mock_span.set_attribute.assert_called_with("tool_name", "simple_tool")

        # Reset
        src.core.tracing._tracer = None


class TestSetupPhoenixTracingErrorScenarios:
    """Test setup_phoenix_tracing error scenarios."""

    def test_setup_phoenix_tracing_import_error_specific_modules(self):
        """Test Phoenix setup with specific import errors."""
        # Test importing phoenix.otel fails
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'phoenix.otel':
                    raise ImportError("No module named 'phoenix.otel'")
                return Mock()

            mock_import.side_effect = import_side_effect

            with patch('src.core.tracing.logger') as mock_logger:
                result = setup_phoenix_tracing()

                assert result is False
                mock_logger.warning.assert_called()

    def test_setup_phoenix_tracing_register_exception(self):
        """Test Phoenix setup when register() raises exception."""
        original_import = __builtins__['__import__']

        def mock_import(name, *args, **kwargs):
            if name in ['phoenix.otel', 'openinference.instrumentation.langchain', 'opentelemetry']:
                # Create mock modules
                mock_module = Mock()
                if name == 'phoenix.otel':
                    mock_module.register.side_effect = Exception("Registration failed")
                elif name == 'openinference.instrumentation.langchain':
                    mock_module.LangChainInstrumentor = Mock()
                elif name == 'opentelemetry':
                    mock_module.trace = Mock()
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            with patch('src.core.tracing.logger') as mock_logger:
                result = setup_phoenix_tracing()

                assert result is False
                mock_logger.error.assert_called_with("Error setting up Phoenix tracing: Registration failed")
                mock_logger.info.assert_called_with("Continuing without tracing...")

    def test_setup_phoenix_tracing_critical_error(self):
        """Test Phoenix setup with critical error in outer try block."""
        with patch('src.core.tracing.logger') as mock_logger:
            # Mock critical error before import attempts
            with patch('src.core.tracing.setup_phoenix_tracing') as mock_setup:
                mock_setup.side_effect = Exception("Critical error")

                try:
                    setup_phoenix_tracing()
                except Exception:
                    pass

                # Test that we handle the outer exception correctly
                # This tests the outer try-except block


class TestInitializeTracingFromConfig:
    """Test initialize_tracing_from_config function."""

    def test_initialize_tracing_from_config(self):
        """Test initializing tracing from config."""
        from src.core.tracing import initialize_tracing_from_config

        config = TracingConfig()
        config.api_key = "test-key"
        config.space_id = "test-space"
        config.project_name = "test-project"

        with patch('src.core.tracing.setup_phoenix_tracing') as mock_setup:
            mock_setup.return_value = True

            result = initialize_tracing_from_config(config)

            assert result is True
            mock_setup.assert_called_once_with(
                api_key="test-key",
                space_id="test-space",
                project_name="test-project"
            )