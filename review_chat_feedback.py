"""Inspect/review local feedback. This operation is deliberately not a public API."""

import argparse
import json
from pathlib import Path

from chat_feedback import DEFAULT_DATABASE, FeedbackStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--status", choices=["pending", "approved", "rejected"], default="pending")
    parser.add_argument("--id", type=int)
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    parser.add_argument("--reviewer")
    parser.add_argument("--note")
    parser.add_argument("--messages-file", type=Path,
                        help="Reviewed JSON list of user/assistant messages; remove personal data and old measurements")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--kind", choices=["dialogue", "knowledge"], default="dialogue")
    parser.add_argument("--data-policy", choices=["static", "hypothetical"], default="static")
    parser.add_argument("--privacy-reviewed", action="store_true")
    parser.add_argument("--facts-reviewed", action="store_true")
    args = parser.parse_args()
    store = FeedbackStore(args.database)
    if args.approve or args.reject:
        if not args.id or not args.reviewer or not args.note or (args.approve and not args.messages_file):
            parser.error("Review requires --id, --reviewer, --note; approval also requires --messages-file.")
        messages = json.loads(args.messages_file.read_text(encoding="utf-8-sig")) if args.messages_file else None
        store.review(args.id, approve=args.approve, reviewer=args.reviewer, note=args.note,
                     messages=messages, source_ids=args.source, kind=args.kind,
                     privacy_reviewed=args.privacy_reviewed, facts_reviewed=args.facts_reviewed,
                     data_policy=args.data_policy)
        print(json.dumps({"reviewed": args.id, "approved": args.approve}, ensure_ascii=False))
    else:
        print(json.dumps(store.list(args.status), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
