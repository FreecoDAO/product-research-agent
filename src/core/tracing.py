"""Arize Phoenix tracing setup for observability."""

import os
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer = None
_tracer_provider = None


def setup_phoenix_tracing(
    api_key: Optional[str] = None,
    space_id: Optional[str] = None,
    project_name: str = "product-research-agent"
) -> bool:
    """
    Set up Arize Phoenix tracing for the application.

    Args:
        api_key: Arize API key (optional for local development)
        space_id: Arize space ID (optional for local development)
        project_name: Project name for tracing

    Returns:
        True if setup successful, False otherwise
    """
    global _tracer, _tracer_provider

    try:
        # Try to import minimal tracing dependencies
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk import trace as trace_sdk
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
            from opentelemetry.sdk.resources import Resource
        except ImportError as e:
            logger.warning(f"Tracing dependencies not available: {e}")
            logger.info("Tracing will be disabled. Install with: pip install openinference-instrumentation-langchain opentelemetry-sdk")
            return False

        # Check if already initialized
        if _tracer is not None:
            logger.debug("Tracing already initialized")
            return True

        # Configure tracer using OpenTelemetry
        try:
            if api_key and space_id:
                # Cloud/production setup using Arize endpoints
                logger.info(f"Setting up Phoenix cloud tracing for project: {project_name}")

                # Configure OTLP exporter for Arize Cloud
                span_exporter = OTLPSpanExporter(
                    endpoint="https://otlp.arize.com/v1/traces",
                    headers={
                        "space_id": space_id,
                        "api_key": api_key,
                    }
                )

                # Create tracer provider
                _tracer_provider = trace_sdk.TracerProvider(
                    resource=Resource.create({
                        "service.name": project_name,
                        "service.version": "1.0.0"
                    })
                )

                # Add span processor
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(span_exporter)
                )

                # Set global tracer provider
                trace.set_tracer_provider(_tracer_provider)

            else:
                # Local development setup using console output
                logger.info(f"Setting up local console tracing for project: {project_name}")

                # Use console exporter for local development
                span_exporter = ConsoleSpanExporter()

                # Create tracer provider
                _tracer_provider = trace_sdk.TracerProvider(
                    resource=Resource.create({
                        "service.name": project_name,
                        "service.version": "1.0.0"
                    })
                )

                # Add span processor
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(span_exporter)
                )

                # Set global tracer provider
                trace.set_tracer_provider(_tracer_provider)

            # Get tracer instance
            _tracer = trace.get_tracer(__name__)

            # Instrument LangChain (covers DeepAgents and LangGraph) only if not already instrumented
            try:
                instrumentor = LangChainInstrumentor()
                if not instrumentor.is_instrumented_by_opentelemetry:
                    instrumentor.instrument()
                    logger.info("LangChain instrumentation enabled")
                else:
                    logger.debug("LangChain already instrumented")
            except Exception as e:
                logger.warning(f"LangChain instrumentation failed: {e}")

            logger.info("Tracing setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error setting up Phoenix tracing: {e}")
            logger.info("Continuing without tracing...")
            return False

    except Exception as e:
        logger.error(f"Critical error in Phoenix setup: {e}")
        return False


def get_tracer():
    """Get the global tracer instance."""
    return _tracer


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return _tracer is not None


@contextmanager
def trace_operation(operation_name: str, **attributes):
    """
    Context manager for tracing operations.

    Args:
        operation_name: Name of the operation being traced
        **attributes: Additional attributes to add to the span
    """
    if not _tracer:
        # No-op if tracing not enabled
        yield None
        return

    try:
        with _tracer.start_as_current_span(operation_name) as span:
            # Add custom attributes
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))

            yield span

    except Exception as e:
        logger.error(f"Error in trace operation {operation_name}: {e}")
        yield None


def add_span_attributes(span, **attributes):
    """
    Add attributes to a span safely.

    Args:
        span: OpenTelemetry span object
        **attributes: Attributes to add
    """
    if not span:
        return

    try:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, str(value))
    except Exception as e:
        logger.error(f"Error adding span attributes: {e}")


def log_research_metrics(
    span,
    query: str,
    num_products: int = 0,
    num_reviews: int = 0,
    total_time: float = 0.0,
    success: bool = True,
    error: str = None
):
    """
    Log research-specific metrics to a span.

    Args:
        span: OpenTelemetry span
        query: Original search query
        num_products: Number of products found
        num_reviews: Number of reviews analyzed
        total_time: Total research time in seconds
        success: Whether research was successful
        error: Error message if research failed
    """
    if not span:
        return

    try:
        add_span_attributes(
            span,
            query=query,
            num_products_found=num_products,
            num_reviews_analyzed=num_reviews,
            total_research_time_seconds=total_time,
            research_success=success
        )

        if error:
            span.set_attribute("error_message", error)
            span.set_status(trace.Status(trace.StatusCode.ERROR, error))

    except Exception as e:
        logger.error(f"Error logging research metrics: {e}")


def log_agent_metrics(
    span,
    agent_name: str,
    operation: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
    latency: float = 0.0
):
    """
    Log agent-specific metrics to a span.

    Args:
        span: OpenTelemetry span
        agent_name: Name of the agent
        operation: Operation performed
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Estimated cost
        latency: Operation latency in seconds
    """
    if not span:
        return

    try:
        add_span_attributes(
            span,
            agent_name=agent_name,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            latency_seconds=latency
        )

    except Exception as e:
        logger.error(f"Error logging agent metrics: {e}")


class TracingConfig:
    """Configuration for tracing setup."""

    def __init__(self):
        self.enabled = False
        self.api_key = None
        self.space_id = None
        self.project_name = "product-research-agent"

    def from_settings(self, settings):
        """Configure from application settings."""
        self.api_key = getattr(settings, 'phoenix_api_key', None)
        self.space_id = getattr(settings, 'phoenix_space_id', None)
        self.project_name = getattr(settings, 'phoenix_project_name', 'product-research-agent')
        return self

    def from_env(self):
        """Configure from environment variables."""
        self.api_key = os.getenv('PHOENIX_API_KEY') or os.getenv('ARIZE_API_KEY')
        self.space_id = os.getenv('PHOENIX_SPACE_ID') or os.getenv('ARIZE_SPACE_ID')
        self.project_name = os.getenv('PHOENIX_PROJECT_NAME', 'product-research-agent')
        return self


def initialize_tracing_from_config(config: TracingConfig) -> bool:
    """
    Initialize tracing from configuration.

    Args:
        config: TracingConfig instance

    Returns:
        True if successful, False otherwise
    """
    return setup_phoenix_tracing(
        api_key=config.api_key,
        space_id=config.space_id,
        project_name=config.project_name
    )


# Convenience functions for common tracing patterns

@contextmanager
def trace_product_research(query: str):
    """Trace a complete product research operation."""
    with trace_operation("product_research", query=query) as span:
        yield span


@contextmanager
def trace_agent_operation(agent_name: str, operation: str):
    """Trace an agent operation."""
    with trace_operation(f"{agent_name}_{operation}", agent_name=agent_name, operation=operation) as span:
        yield span


@contextmanager
def trace_tool_usage(tool_name: str, input_params: dict = None):
    """Trace tool usage."""
    with trace_operation(f"tool_{tool_name}", tool_name=tool_name) as span:
        if input_params and span:
            for key, value in input_params.items():
                span.set_attribute(f"input_{key}", str(value))
        yield span


# Initialize tracing on module import if environment variables are set
def _auto_initialize():
    """Auto-initialize tracing if environment is configured."""
    try:
        config = TracingConfig().from_env()
        if config.api_key or os.getenv('PHOENIX_AUTO_INIT', '').lower() == 'true':
            logger.info("Auto-initializing Phoenix tracing from environment")
            initialize_tracing_from_config(config)
    except Exception as e:
        logger.debug(f"Auto-initialization skipped: {e}")


# Auto-initialize on import
_auto_initialize()