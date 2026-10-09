from __future__ import annotations

import argparse

from .common import repo_path, utc_now, write_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("stage")
    parser.add_argument("exit_code", type=int)
    args = parser.parse_args()
    status = "completed" if args.exit_code == 0 else ("invalid" if args.exit_code == 2 else "incomplete")
    write_receipt(
        repo_path(args.run_dir), args.stage, status, utc_now(), None, None, tools=["bash"],
        errors=[] if args.exit_code == 0 else [f"orchestrator exit code {args.exit_code}"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
