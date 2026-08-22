"""Comprehensive Test Suite — Sprint 12A AWS Infrastructure Foundation (55 tests)."""

import ast
import pathlib
import threading
import time
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from infrastructure.aws_config import AWSConfig, AWSConfigManager, AWSEnvironment
from infrastructure.aws_credentials import AWSCredentialManager, AWSCredentialsDescriptor
from infrastructure.aws_session import AWSSessionManager, MockAWSClient, SessionRecord
from infrastructure.cloudwatch_logger import CloudWatchLogEvent, CloudWatchLogger, LogLevel
from infrastructure.infrastructure_events import (
    CredentialsLoaded,
    InfrastructureInitialized,
    LogBatchFlushed,
    ObjectDownloaded,
    ObjectUploaded,
    ParameterRegistered,
    SecretRegistered,
    SessionCreated,
)
from infrastructure.infrastructure_manager import InfrastructureManager
from infrastructure.parameter_store import ParameterDescriptor, ParameterStore
from infrastructure.s3_storage import S3ObjectMetadata, S3Storage
from infrastructure.secrets_manager import SecretDescriptor, SecretsManager
from toji_platform.core.event_bus import InMemoryEventBus


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def infra_mgr(event_bus):
    return InfrastructureManager(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 1. AWS Configuration (Tests 1–5)
# ---------------------------------------------------------------------------
def test_config_defaults():
    cfg = AWSConfig()
    assert cfg.region == "us-east-1"
    assert cfg.environment == AWSEnvironment.DEV
    assert cfg.is_advisory_only is True


def test_config_custom_values():
    cfg = AWSConfig(region="us-west-2", environment=AWSEnvironment.PROD, timeout_seconds=15.0)
    assert cfg.region == "us-west-2"
    assert cfg.environment == AWSEnvironment.PROD
    assert cfg.timeout_seconds == 15.0


def test_config_invalid_empty_region():
    with pytest.raises(ValidationError):
        AWSConfig(region="")


def test_config_manager_load():
    cfg = AWSConfigManager.load_config(overrides={"region": "eu-central-1"})
    assert cfg.region == "eu-central-1"


def test_config_immutability():
    cfg = AWSConfig()
    with pytest.raises((ValidationError, TypeError)):
        cfg.region = "ap-southeast-1"


# ---------------------------------------------------------------------------
# 2. Credential Manager (Tests 6–10)
# ---------------------------------------------------------------------------
def test_credentials_descriptor_masking():
    cm = AWSCredentialManager(access_key_id="AKIAIOSFODNN7EXAMPLE")
    desc = cm.get_descriptor()
    assert desc.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert "AKIA****LE" == desc.access_key_id_masked
    assert desc.is_advisory_only is True


def test_credentials_validation_success():
    cm = AWSCredentialManager(access_key_id="AKIA_VALID", secret_access_key="SECRET_VALID")
    assert cm.validate_credentials() is True


def test_credentials_validation_failure():
    cm = AWSCredentialManager(access_key_id="", secret_access_key="")
    assert cm.validate_credentials() is False


def test_credentials_refresh_session():
    cm = AWSCredentialManager()
    desc = cm.refresh_session(new_token="SESSION_TOKEN_123")
    assert desc.has_session_token is True


def test_credentials_never_expose_secrets_in_str():
    cm = AWSCredentialManager(secret_access_key="SUPER_CONFIDENTIAL_SECRET")
    desc = cm.get_descriptor()
    assert "SUPER_CONFIDENTIAL_SECRET" not in str(desc)
    assert "SUPER_CONFIDENTIAL_SECRET" not in repr(desc)


# ---------------------------------------------------------------------------
# 3. Session Lifecycle & Injection (Tests 11–15)
# ---------------------------------------------------------------------------
def test_session_lazy_initialization():
    sm = AWSSessionManager()
    assert sm._session_record is None
    sess = sm.get_session()
    assert sess is not None
    assert sm._session_record is not None


def test_session_reuse():
    sm = AWSSessionManager()
    s1 = sm.get_session()
    s2 = sm.get_session()
    assert s1.session_id == s2.session_id


def test_session_reset():
    sm = AWSSessionManager()
    s1 = sm.get_session()
    sm.reset_session()
    s2 = sm.get_session()
    assert s1.session_id != s2.session_id


def test_session_custom_client_factory():
    calls = []

    def mock_factory(service, cfg):
        calls.append(service)
        return MockAWSClient(service, cfg.region)

    sm = AWSSessionManager(client_factory=mock_factory)
    client = sm.get_client("dynamodb")
    assert client.service_name == "dynamodb"
    assert "dynamodb" in calls


def test_session_no_network_calls_on_client():
    sm = AWSSessionManager()
    client = sm.get_client("s3")
    res = client.call_action("list_buckets")
    assert res["status"] == "success"
    assert res["service"] == "s3"


# ---------------------------------------------------------------------------
# 4. Secrets Manager (Tests 16–20)
# ---------------------------------------------------------------------------
def test_secrets_register():
    sec_mgr = SecretsManager()
    desc = sec_mgr.register_secret("db_credentials", description="DB secret ref")
    assert desc.secret_name == "db_credentials"
    assert "db_credentials" in desc.arn


def test_secrets_get_reference():
    sec_mgr = SecretsManager()
    sec_mgr.register_secret("apiKey")
    ref = sec_mgr.get_secret_reference("apiKey")
    assert ref is not None
    assert ref.secret_name == "apiKey"


def test_secrets_list():
    sec_mgr = SecretsManager()
    sec_mgr.register_secret("s1")
    sec_mgr.register_secret("s2")
    assert len(sec_mgr.list_secrets()) == 2


def test_secrets_bounded_eviction():
    sec_mgr = SecretsManager(max_secrets=2)
    sec_mgr.register_secret("s1")
    sec_mgr.register_secret("s2")
    sec_mgr.register_secret("s3")
    assert sec_mgr.count() == 2
    assert sec_mgr.get_secret_reference("s1") is None


def test_secrets_never_store_plain_values():
    desc = SecretDescriptor(secret_name="my_secret", arn="arn:aws:sm:123:secret:my_secret")
    assert not hasattr(desc, "secret_value")
    assert not hasattr(desc, "value")


# ---------------------------------------------------------------------------
# 5. Parameter Store (Tests 21–25)
# ---------------------------------------------------------------------------
def test_parameter_register():
    ps = ParameterStore()
    p = ps.register_parameter("max_retries", 5, value_type="String")
    assert p.name == "max_retries"
    assert p.value == 5
    assert p.version == 1


def test_parameter_lookup():
    ps = ParameterStore()
    ps.register_parameter("rate_limit", 100)
    retrieved = ps.get_parameter("rate_limit")
    assert retrieved is not None
    assert retrieved.value == 100


def test_parameter_version_increment():
    ps = ParameterStore()
    p1 = ps.register_parameter("setting", "val1")
    p2 = ps.register_parameter("setting", "val2")
    assert p1.version == 1
    assert p2.version == 2
    assert ps.get_parameter("setting").value == "val2"


def test_parameter_get_specific_version():
    ps = ParameterStore()
    ps.register_parameter("alpha", "v1")
    ps.register_parameter("alpha", "v2")
    v1_desc = ps.get_parameter_version("alpha", version=1)
    assert v1_desc is not None
    assert v1_desc.value == "v1"


def test_parameter_bounded_eviction():
    ps = ParameterStore(max_parameters=2)
    ps.register_parameter("p1", 1)
    ps.register_parameter("p2", 2)
    ps.register_parameter("p3", 3)
    assert ps.count() == 2
    assert ps.get_parameter("p1") is None


# ---------------------------------------------------------------------------
# 6. S3 Storage (Tests 26–30)
# ---------------------------------------------------------------------------
def test_s3_upload_checksum():
    s3 = S3Storage()
    data = b"Hello AWS S3 Abstraction"
    meta = s3.upload_object("mybucket", "logs/data.txt", data, content_type="text/plain")
    assert meta.bucket == "mybucket"
    assert meta.key == "logs/data.txt"
    assert meta.size_bytes == len(data)
    assert len(meta.checksum) == 64  # SHA256 length


def test_s3_download():
    s3 = S3Storage()
    data = b"Test Content"
    s3.upload_object("bucketA", "k1", data)
    downloaded_bytes, meta = s3.download_object("bucketA", "k1")
    assert downloaded_bytes == data
    assert meta.key == "k1"


def test_s3_get_metadata():
    s3 = S3Storage()
    s3.upload_object("bucketB", "k2", b"123")
    meta = s3.get_metadata("bucketB", "k2")
    assert meta is not None
    assert meta.size_bytes == 3


def test_s3_list_by_bucket():
    s3 = S3Storage()
    s3.upload_object("b1", "k1", b"x")
    s3.upload_object("b1", "k2", b"y")
    s3.upload_object("b2", "k3", b"z")

    b1_items = s3.list_objects("b1")
    assert len(b1_items) == 2


def test_s3_download_nonexistent_raises():
    s3 = S3Storage()
    with pytest.raises(KeyError):
        s3.download_object("b_missing", "k_missing")


# ---------------------------------------------------------------------------
# 7. CloudWatch Logger (Tests 31–35)
# ---------------------------------------------------------------------------
def test_cloudwatch_log_enqueue():
    cw = CloudWatchLogger()
    evt = cw.log("Application started", level=LogLevel.INFO, extra={"pid": 1234})
    assert evt.message == "Application started"
    assert evt.level == LogLevel.INFO
    assert evt.extra["pid"] == 1234
    assert cw.queue_size() == 1


def test_cloudwatch_flush_batch():
    cw = CloudWatchLogger()
    cw.log("msg1")
    cw.log("msg2")
    cw.log("msg3")

    flushed = cw.flush_batch(batch_size=2)
    assert len(flushed) == 2
    assert cw.queue_size() == 1
    assert cw.flushed_count() == 2


def test_cloudwatch_severity_levels():
    cw = CloudWatchLogger()
    e_debug = cw.log("d", level=LogLevel.DEBUG)
    e_err = cw.log("e", level=LogLevel.ERROR)
    e_crit = cw.log("c", level=LogLevel.CRITICAL)

    assert e_debug.level == LogLevel.DEBUG
    assert e_err.level == LogLevel.ERROR
    assert e_crit.level == LogLevel.CRITICAL


def test_cloudwatch_queue_bounded_eviction():
    cw = CloudWatchLogger(max_queue_size=2)
    cw.log("m1")
    cw.log("m2")
    cw.log("m3")

    assert cw.queue_size() == 2
    batch = cw.flush_batch(batch_size=10)
    assert batch[0].message == "m2"
    assert batch[1].message == "m3"


def test_cloudwatch_clear():
    cw = CloudWatchLogger()
    cw.log("msg")
    cw.flush_batch()
    cw.clear()
    assert cw.queue_size() == 0
    assert cw.flushed_count() == 0


# ---------------------------------------------------------------------------
# 8. Infrastructure Manager Coordination (Tests 36–40)
# ---------------------------------------------------------------------------
def test_manager_initialize(infra_mgr):
    sess = infra_mgr.initialize()
    assert sess is not None
    assert infra_mgr._initialized is True


def test_manager_register_secret(infra_mgr):
    desc = infra_mgr.register_secret("sec1")
    assert desc.secret_name == "sec1"
    assert infra_mgr.secrets_manager.get_secret_reference("sec1") is not None


def test_manager_register_parameter(infra_mgr):
    desc = infra_mgr.register_parameter("param1", "val1")
    assert desc.name == "param1"
    assert infra_mgr.parameter_store.get_parameter("param1").value == "val1"


def test_manager_s3_upload_download(infra_mgr):
    meta = infra_mgr.upload_s3_object("b", "k", b"hello world")
    assert meta.key == "k"
    data, meta_down = infra_mgr.download_s3_object("b", "k")
    assert data == b"hello world"


def test_manager_cloudwatch_log_flush(infra_mgr):
    infra_mgr.log_cloudwatch("test message")
    batch = infra_mgr.flush_cloudwatch_logs()
    assert len(batch) == 1
    assert batch[0].message == "test message"


# ---------------------------------------------------------------------------
# 9. Events (Tests 41–48)
# ---------------------------------------------------------------------------
def test_event_infrastructure_initialized(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("InfrastructureInitialized", lambda e: evts.append(e))
    infra_mgr.initialize()
    assert len(evts) == 1
    assert evts[0].event_type == "InfrastructureInitialized"


def test_event_credentials_loaded(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("CredentialsLoaded", lambda e: evts.append(e))
    infra_mgr.initialize()
    assert len(evts) == 1
    assert evts[0].event_type == "CredentialsLoaded"


def test_event_session_created(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("SessionCreated", lambda e: evts.append(e))
    infra_mgr.initialize()
    assert len(evts) == 1
    assert evts[0].event_type == "SessionCreated"


def test_event_secret_registered(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("SecretRegistered", lambda e: evts.append(e))
    infra_mgr.register_secret("s_evt")
    assert len(evts) == 1
    assert evts[0].secret_name == "s_evt"


def test_event_parameter_registered(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("ParameterRegistered", lambda e: evts.append(e))
    infra_mgr.register_parameter("p_evt", 100)
    assert len(evts) == 1
    assert evts[0].parameter_name == "p_evt"


def test_event_object_uploaded(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("ObjectUploaded", lambda e: evts.append(e))
    infra_mgr.upload_s3_object("b", "k", b"abc")
    assert len(evts) == 1
    assert evts[0].key == "k"


def test_event_object_downloaded(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("ObjectDownloaded", lambda e: evts.append(e))
    infra_mgr.upload_s3_object("b", "k", b"abc")
    infra_mgr.download_s3_object("b", "k")
    assert len(evts) == 1
    assert evts[0].key == "k"


def test_event_log_batch_flushed(event_bus, infra_mgr):
    evts = []
    event_bus.subscribe("LogBatchFlushed", lambda e: evts.append(e))
    infra_mgr.log_cloudwatch("evt_msg")
    infra_mgr.flush_cloudwatch_logs()
    assert len(evts) == 1
    assert evts[0].event_count == 1


# ---------------------------------------------------------------------------
# 10. Thread Safety & Performance (Tests 49–51)
# ---------------------------------------------------------------------------
def test_thread_safety_concurrent_operations(infra_mgr):
    errors = []

    def worker(i):
        try:
            for j in range(5):
                sec_name = f"sec_{i}_{j}"
                infra_mgr.register_secret(sec_name)
                infra_mgr.register_parameter(f"param_{i}_{j}", j)
                infra_mgr.upload_s3_object("bucket", f"key_{i}_{j}", b"data")
                infra_mgr.log_cloudwatch(f"log_{i}_{j}")
        except Exception as ex:
            errors.append(ex)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert infra_mgr.secrets_manager.count() == 25
    assert infra_mgr.parameter_store.count() == 25


def test_performance_1000_secrets():
    sec_mgr = SecretsManager(max_secrets=1500)
    start_t = time.perf_counter()

    for i in range(1000):
        sec_mgr.register_secret(f"sec_scale_{i}")

    elapsed = time.perf_counter() - start_t
    assert sec_mgr.count() == 1000
    assert elapsed < 5.0  # Must be fast under capacity


def test_performance_10000_parameters():
    ps = ParameterStore(max_parameters=12000)
    start_t = time.perf_counter()

    for i in range(10000):
        ps.register_parameter(f"param_scale_{i}", i)

    elapsed = time.perf_counter() - start_t
    assert ps.count() == 10000
    assert elapsed < 5.0  # Must be fast under capacity


# ---------------------------------------------------------------------------
# 11. Dependency Injection & Mockability (Tests 52–53)
# ---------------------------------------------------------------------------
def test_dependency_injection_custom_session_manager():
    sm = AWSSessionManager()
    mgr = InfrastructureManager(session_mgr=sm)
    assert mgr.session_manager is sm


def test_mockable_s3_backend():
    class MockS3Backend(S3Storage):
        def upload_object(self, bucket, key, data, content_type="application/octet-stream", metadata_dict=None):
            return S3ObjectMetadata(bucket=bucket, key=key, size_bytes=999, checksum="MOCK_CHECKSUM")

    mock_s3 = MockS3Backend()
    mgr = InfrastructureManager(s3_storage=mock_s3)
    meta = mgr.upload_s3_object("b", "k", b"data")
    assert meta.size_bytes == 999
    assert meta.checksum == "MOCK_CHECKSUM"


# ---------------------------------------------------------------------------
# 12. Architecture Boundary Enforcement & Regression (Tests 54–55)
# ---------------------------------------------------------------------------
def test_regression_sprint11c_unaffected():
    from self_learning.evaluation_manager import EvaluationManager
    eval_mgr = EvaluationManager()
    rec = eval_mgr.create_evaluation("m1", "d1")
    assert rec.model_id == "m1"
    assert rec.is_advisory_only is True


def test_architecture_boundary_enforcement():
    infra_dir = pathlib.Path(__file__).parent.parent / "infrastructure"
    forbidden = {"broker", "strategy", "execution", "live_trading", "paper_trading"}

    violations = []
    for py_file in infra_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        if f in alias.name:
                            violations.append(f"Forbidden import '{alias.name}' in {py_file.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for f in forbidden:
                        if f in node.module:
                            violations.append(f"Forbidden from-import '{node.module}' in {py_file.name}")

    assert violations == [], f"Architecture violations found: {violations}"
