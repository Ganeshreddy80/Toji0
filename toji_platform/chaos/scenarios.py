"""List of registered chaos scenarios."""

from toji_platform.chaos.registry import registry

def register_scenarios() -> None:
    """Register scenario metadata and handler callbacks in registry."""
    registry.register("plugin_init_failure", lambda injector, cfg: injector.enable_scenario("plugin_init_failure", cfg))
    registry.register("plugin_shutdown_failure", lambda injector, cfg: injector.enable_scenario("plugin_shutdown_failure", cfg))
    registry.register("lifecycle_startup_failure", lambda injector, cfg: injector.enable_scenario("lifecycle_startup_failure", cfg))
    registry.register("lifecycle_shutdown_failure", lambda injector, cfg: injector.enable_scenario("lifecycle_shutdown_failure", cfg))
    registry.register("event_bus_publish_failure", lambda injector, cfg: injector.enable_scenario("event_bus_publish_failure", cfg))
    registry.register("event_bus_handler_exception", lambda injector, cfg: injector.enable_scenario("event_bus_handler_exception", cfg))
    registry.register("heartbeat_timeout", lambda injector, cfg: injector.enable_scenario("heartbeat_timeout", cfg))
    registry.register("kernel_boot_failure", lambda injector, cfg: injector.enable_scenario("kernel_boot_failure", cfg))
    registry.register("kernel_shutdown_failure", lambda injector, cfg: injector.enable_scenario("kernel_shutdown_failure", cfg))
    registry.register("memory_pressure", lambda injector, cfg: injector.enable_scenario("memory_pressure", cfg))
    registry.register("cpu_spike", lambda injector, cfg: injector.enable_scenario("cpu_spike", cfg))
    registry.register("thread_failure", lambda injector, cfg: injector.enable_scenario("thread_failure", cfg))
    registry.register("delayed_component_startup", lambda injector, cfg: injector.enable_scenario("delayed_component_startup", cfg))
    registry.register("delayed_component_shutdown", lambda injector, cfg: injector.enable_scenario("delayed_component_shutdown", cfg))

register_scenarios()
