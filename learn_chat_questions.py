"""Inspect local question learning or recheck it against an updated knowledge base."""
import argparse
import json
from pathlib import Path

from chat_learning import ConversationLearner, DEFAULT_DATABASE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--pending", action="store_true", help="Show questions still needing a checked source")
    parser.add_argument("--recheck", action="store_true", help="Recheck questions after the verified knowledge base changes")
    args = parser.parse_args()
    learner = ConversationLearner(args.database)
    rechecked = learner.recheck() if args.recheck else 0
    result = {"enabled": learner.enabled, "counts": learner.stats(), "rechecked": rechecked,
              "trainable_records": len(learner.training_records())}
    if args.pending:
        result["questions_needing_sources"] = learner.questions("needs_source")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
