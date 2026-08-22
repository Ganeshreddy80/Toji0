import os
import pytest
from toji_platform.kernel import TojiKernel
from toji_platform.chaos.injector import chaos_injector
from toji_platform.core.errors import PluginLoadError, StartupError

@pytest.fixture(autouse=True)
def setup_chaos_env():
    # Enable chaos by default in tests
    os.environ["TOJI_CHAOS_ENABLED"] = "true"
    yield
    # Cleanup after each test
    chaos_injector.reset()
    if "TOJI_CHAOS_ENABLED" in os.environ:
        del os.environ["TOJI_CHAOS_ENABLED"]

def test_chaos_production_disabled():
    """Chaos must never activate when disabled/missing from environment."""
    os.environ["TOJI_CHAOS_ENABLED"] = "false"

    # Try enabling plugin init failure
    chaos_injector.enable_scenario("plugin_init_failure")

    # Verify kernel boots successfully (i.e. patch did not take effect)
    kernel = TojiKernel()
    kernel.boot()
    assert kernel.is_booted is True
    kernel.shutdown()

def test_chaos_plugin_init_failure():
    chaos_injector.enable_scenario("plugin_init_failure")
    kernel = TojiKernel()
    with pytest.raises(PluginLoadError, match="Chaos: plugin init failed"):
        kernel.boot()

def test_chaos_plugin_shutdown_failure():
    kernel = TojiKernel()
    kernel.boot()
    chaos_injector.enable_scenario("plugin_shutdown_failure")

    # Plugin shutdown fails and propagates the exception, but finally transitions to stopped
    with pytest.raises(RuntimeError, match="Chaos: plugin shutdown failed"):
        kernel.shutdown()
    assert kernel.is_booted is False

def test_chaos_lifecycle_startup_failure():
    chaos_injector.enable_scenario("lifecycle_startup_failure")
    kernel = TojiKernel()
    with pytest.raises(StartupError, match="Chaos: lifecycle startup failed"):
        kernel.boot()

def test_chaos_lifecycle_shutdown_failure():
    kernel = TojiKernel()
    kernel.boot()
    chaos_injector.enable_scenario("lifecycle_shutdown_failure")

    from toji_platform.core.errors import ShutdownError
    with pytest.raises(ShutdownError, match="Chaos: lifecycle shutdown failed"):
        kernel.shutdown()

def test_chaos_heartbeat_timeout():
    chaos_injector.enable_scenario("heartbeat_timeout")
    kernel = TojiKernel()
    kernel.boot()
    # Heartbeat scheduler shouldn't have started a thread
    assert kernel._heartbeat_scheduler._thread is None
    kernel.shutdown()

def test_chaos_kernel_boot_failure():
    chaos_injector.enable_scenario("kernel_boot_failure")
    kernel = TojiKernel()
    with pytest.raises(RuntimeError, match="Chaos: kernel boot failed"):
        kernel.boot()

def test_chaos_kernel_shutdown_failure():
    kernel = TojiKernel()
    kernel.boot()
    chaos_injector.enable_scenario("kernel_shutdown_failure")
    with pytest.raises(RuntimeError, match="Chaos: kernel shutdown failed"):
        kernel.shutdown()

def test_chaos_enable_disable_behaviour():
    kernel = TojiKernel()

    # Fails when enabled
    chaos_injector.enable_scenario("plugin_init_failure")
    with pytest.raises(PluginLoadError):
        kernel.boot()

    # Succeeds when disabled
    chaos_injector.disable_scenario("plugin_init_failure")
    kernel.boot()
    assert kernel.is_booted is True
    kernel.shutdown()

def test_chaos_reset_behaviour():
    chaos_injector.enable_scenario("plugin_init_failure")
    chaos_injector.enable_scenario("lifecycle_startup_failure")

    # Reset all
    chaos_injector.reset()

    kernel = TojiKernel()
    kernel.boot()
    assert kernel.is_booted is True
    kernel.shutdown()
