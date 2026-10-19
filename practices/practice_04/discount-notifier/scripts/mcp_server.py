"""Launch from the application root, independent of the caller's working directory."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)

if __name__=='__main__':
    from app.mcp_server import main
    main()
