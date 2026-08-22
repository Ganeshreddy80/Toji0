# VALIDATION.md — Continuous System Health Monitoring

Continuous Validation (R53) runs diagnostic checkers evaluating platform status parameters.

## Active Health Checkers
1. **MemoryChecker**: Monitors memory growth and warns on RSS usage exceeding 1GB.
2. **ThreadChecker**: Traces thread leaks.
3. **DeadlockChecker**: Identifies lock contention.
4. **DatabaseChecker**: Pings database session connections.
5. **SchedulerChecker**: Validates chronologies.
6. **IntegrityChecker**: Verifies portfolio weights sum to exactly ~1.0.
