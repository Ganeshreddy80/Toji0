#!/usr/bin/env python3
import sys
import os
import uvicorn

# Configure environment defaults for run_api
if not os.getenv("MARKET_PROVIDER"):
    os.environ["MARKET_PROVIDER"] = "demo"

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.state import PlatformState

# 1. Boot platform kernel to populate PlatformState
kernel = bootstrap_platform()

# 2. Import FastAPI app (which will attach to the existing kernel via PlatformState)
from backend.main import app

# 3. Start uvicorn
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
