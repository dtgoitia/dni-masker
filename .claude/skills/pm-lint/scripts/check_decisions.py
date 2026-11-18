#!/usr/bin/env python3
"""Check the links between question items and their decision records.

A decision (PDR-nnnn in product/decisions/pdrs/, ADR-nnnn in
product/decisions/adrs/) answers one question item through its `question:`
field, and the question points back with its `decision:` field. Reports on
stderr (exit code 1 if anything is found):
  - misplaced: a decision outside its kind's directory
  - missing question: a decision without a `question` field
  - unknown ID: a `question` or `decision` that doesn't exist
  - not a question: a decision answering a non-question item, or a
    non-question item with a `decision` field
  - out of sync: one side of the link doesn't point back
  - missing decision: a `done` question without a `decision`
Problems are sorted by the ID of the file they were found on.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from _items import DECISION_DIRS, Decision, Item, load_decisions, load_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-dir", default="product", help="product directory (default: ./product)")
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    if not (product_dir / "items").is_dir():
        print(f"error: items directory not found: {(product_dir / 'items').resolve()}", file=sys.stderr)
        return 2

    items: dict[str, list[Item]] = defaultdict(list)
    for item in load_items(product_dir):
        if item.id:
            items[item.id].append(item)
    decisions: dict[str, list[Decision]] = defaultdict(list)
    for decision in load_decisions(product_dir):
        if decision.id:
            decisions[decision.id].append(decision)

    problems: list[tuple[str, str]] = []  # (ID it was found on, message)

    for decision_id, found in decisions.items():
        for decision in found:
            directory = product_dir / "decisions" / DECISION_DIRS[decision_id[:3]]
            if decision.path.parent != directory:
                problems.append((decision_id, f"misplaced: {decision_id} is not in decisions/{directory.name}/ "
                                              f"({decision.path})"))
            question_id = decision.question
            if not question_id:
                problems.append((decision_id, f"missing question: {decision_id} has no `question` field ({decision.path})"))
            elif question_id not in items:
                problems.append((decision_id, f"unknown ID: {decision_id} question {question_id}, which doesn't exist "
                                              f"({decision.path})"))
            else:
                for question in items[question_id]:
                    if question.type != "question":
                        problems.append((decision_id, f"not a question: {decision_id} question {question_id}, "
                                                      f"which is a {question.type} ({decision.path})"))
                    elif not question.decision:
                        problems.append((decision_id, f"out of sync: {decision_id} question {question_id}, "
                                                      f"but {question_id} has no `decision` ({question.path})"))
                    elif question.decision != decision_id:
                        problems.append((decision_id, f"out of sync: {decision_id} question {question_id}, "
                                                      f"but {question_id} has decision {question.decision} "
                                                      f"({question.path})"))

    for item_id, found in items.items():
        for item in found:
            if item.decision and item.type != "question":
                problems.append((item_id, f"not a question: {item_id} has decision {item.decision}, "
                                          f"but is a {item.type} ({item.path})"))
            if not item.decision:
                if item.type == "question" and item.status == "done":
                    problems.append((item_id, f"missing decision: {item_id} is done but has no `decision` "
                                              f"({item.path})"))
            elif item.decision not in decisions:
                problems.append((item_id, f"unknown ID: {item_id} decision {item.decision}, which doesn't exist "
                                          f"({item.path})"))
            elif item.type == "question":
                for decision in decisions[item.decision]:
                    if decision.question and decision.question != item_id:
                        problems.append((item_id, f"out of sync: {item_id} decision {item.decision}, "
                                                  f"but {item.decision} has question {decision.question} "
                                                  f"({decision.path})"))

    for _, problem in sorted(problems, key=lambda p: p[0]):
        print(problem, file=sys.stderr)
    if not problems:
        print("no decision problems found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
