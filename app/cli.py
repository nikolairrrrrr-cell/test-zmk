from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import Settings
from app.recognizers import AgentRecognizer, AgentReadRequired, RecognitionError
from app.use_cases.pdf_zmk import run_pdf_zmk_full
from app.use_cases.pdf_zmk2 import run_pdf_zmk2
from app.use_cases.ves import run_ves


EXIT_OK = 0
EXIT_INVALID_INPUT = 2
EXIT_AGENT_READ = 3
EXIT_RUNTIME = 5


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="test-zmk")
    root_sub = parser.add_subparsers(dest="tool", required=True)

    # pdf-zmk
    pdf_zmk = root_sub.add_parser("pdf-zmk")
    pdf_zmk_sub = pdf_zmk.add_subparsers(dest="command", required=True)
    pdf_zmk_full = pdf_zmk_sub.add_parser("full")
    pdf_zmk_full.add_argument("--input-dir", required=True)
    pdf_zmk_full.add_argument("--sheet-write", action="store_true")
    pdf_zmk_full.add_argument("--dry-run", action="store_true")
    pdf_zmk_full.add_argument("--workers", type=int, default=6)
    pdf_zmk_full.add_argument("--output-json")

    # pdf-zmk2
    pdf_zmk2 = root_sub.add_parser("pdf-zmk2")
    pdf_zmk2_sub = pdf_zmk2.add_subparsers(dest="command", required=True)
    pdf_zmk2_run = pdf_zmk2_sub.add_parser("run")
    pdf_zmk2_run.add_argument("--input", required=True)
    pdf_zmk2_run.add_argument("--sheet-write", action="store_true")
    pdf_zmk2_run.add_argument("--dry-run", action="store_true")
    pdf_zmk2_run.add_argument("--output-json")

    # ves
    ves = root_sub.add_parser("ves")
    ves_sub = ves.add_subparsers(dest="command", required=True)
    ves_run = ves_sub.add_parser("run")
    ves_run.add_argument("--positions", required=True)
    ves_run.add_argument("--online", action="store_true")
    ves_run.add_argument("--force-refresh", action="store_true")
    ves_run.add_argument("--sheet-write", action="store_true")
    ves_run.add_argument("--dry-run", action="store_true")
    ves_run.add_argument("--output-json")
    ves_run.add_argument("--db-path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    recognizer = AgentRecognizer()

    try:
        if args.tool == "pdf-zmk" and args.command == "full":
            result = run_pdf_zmk_full(
                input_dir=Path(args.input_dir),
                settings=settings,
                sheet_write=bool(args.sheet_write),
                dry_run=bool(args.dry_run),
                output_json=Path(args.output_json) if args.output_json else None,
                workers=int(args.workers),
            )
            print(
                "pdf-zmk full done: "
                f"total={result.total_files}, processed={result.processed_files}, "
                f"skipped={result.skipped_files}, rows={result.rows_count}, "
                f"elapsed={result.elapsed_seconds}s, "
                f"sheet_written={result.sheet_written}"
            )
            return EXIT_OK

        if args.tool == "pdf-zmk2" and args.command == "run":
            run_pdf_zmk2(
                input_path=Path(args.input),
                recognizer=recognizer,
                settings=settings,
                sheet_write=bool(args.sheet_write),
                dry_run=bool(args.dry_run),
                output_json=Path(args.output_json) if args.output_json else None,
            )
            return EXIT_OK

        if args.tool == "ves" and args.command == "run":
            run_ves(
                positions_path=Path(args.positions),
                settings=settings,
                sheet_write=bool(args.sheet_write),
                dry_run=bool(args.dry_run),
                online=bool(args.online),
                force_refresh=bool(args.force_refresh),
                output_json=Path(args.output_json) if args.output_json else None,
                db_path=Path(args.db_path) if args.db_path else None,
            )
            return EXIT_OK

        parser.print_help()
        return EXIT_INVALID_INPUT

    except AgentReadRequired as exc:
        print(
            "\n╔══════════════════════════════════════════════════╗\n"
            "║  AGENT_READ_REQUIRED                             ║\n"
            "╚══════════════════════════════════════════════════╝\n",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        print(
            "\n→ Agent must now read each crop image listed above,\n"
            "  extract the table data, and write the JSON payload.\n"
            "→ Then re-run: python -m app.cli pdf-zmk full --input-dir <dir> --sheet-write\n",
            file=sys.stderr,
        )
        return EXIT_AGENT_READ

    except (ValueError, RecognitionError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    except Exception as exc:  # pragma: no cover
        print(f"Runtime error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME


if __name__ == "__main__":
    raise SystemExit(main())
