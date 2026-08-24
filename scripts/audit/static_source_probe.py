from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = {
    'open', 'high', 'low', 'close', 'volume', 'log_return', 'atr', 'ema9', 'ema21',
    'ema50', 'rsi', 'volume_change', 'support', 'resistance', 'rolling_std',
    'normalized_atr', 'annualized_vol', 'breakout', 'trend', 'risk_score', 'signal'
}


def tracked_python() -> list[Path]:
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '*.py'], text=True).splitlines()
    return [ROOT / name for name in names]


def main() -> None:
    parse_errors = []
    full_literal_hits = []
    canonical_subset_hits = []
    for path in tracked_python():
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except Exception as exc:
            parse_errors.append({'file': str(path.relative_to(ROOT)), 'error': type(exc).__name__})
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                values = []
                valid = True
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        values.append(elt.value)
                    else:
                        valid = False
                        break
                if not valid or len(values) < 5:
                    continue
                value_set = set(values)
                if value_set == CANONICAL and len(values) == len(CANONICAL):
                    full_literal_hits.append({'file': str(path.relative_to(ROOT)), 'line': node.lineno, 'kind': type(node).__name__})
                elif len(CANONICAL & value_set) >= 10:
                    canonical_subset_hits.append({'file': str(path.relative_to(ROOT)), 'line': node.lineno, 'count': len(CANONICAL & value_set), 'values': sorted(CANONICAL & value_set)})
    print(json.dumps({
        'tracked_python_files': len(tracked_python()),
        'parse_errors': parse_errors,
        'full_canonical_literal_hits': full_literal_hits,
        'canonical_subset_hits': canonical_subset_hits,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
