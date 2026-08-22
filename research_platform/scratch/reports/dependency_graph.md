# TOJI V1 Dependency Graph Report

This report visualizes the internal package-level dependencies scanned across the TOJI Quantitative Research Platform.

```mermaid
graph TD
    research_platform --> research_platform.platform
    research_platform --> research_platform.persistence
    research_platform --> research_platform.config
    research_platform --> research_platform.logging
    research_platform --> research_platform.validation
    research_platform --> research_platform.alerting
    research_platform --> research_platform.metrics
    research_platform --> research_platform.scheduler
    research_platform.platform --> research_platform.persistence
    research_platform.scheduler --> research_platform.validation
    research_platform.validation --> research_platform.alerting
```
