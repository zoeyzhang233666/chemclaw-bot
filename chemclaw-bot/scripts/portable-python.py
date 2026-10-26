"""Make legacy user-provided scripts locate supported runtimes portably."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
changed = []
for file in (root / 'skills/domain').rglob('*.py'):
    text = file.read_text(encoding='utf-8-sig')
    # Match a former maintainer home path without embedding the username in this file.
    marker = 'C:\\Users\\' + 'EDY'
    if marker not in text:
        continue
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode('utf-8')))
    raw = text.encode('utf-8')
    edits = []
    office = 'libreoffice-kit' in text
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value.startswith(marker):
            continue
        value = node.value.lower()
        if 'libreoffice-kit' in value:
            replacement = "str(_CHEMCLAW_ROOT / 'runtime/office-cli.py')"
        elif value.endswith('node.exe'):
            replacement = "__import__('sys').executable" if office else "(__import__('shutil').which('node') or 'node')"
        elif 'chrome' in value:
            replacement = "(__import__('os').environ.get('CHROME_EXE') or __import__('shutil').which('chrome') or __import__('shutil').which('msedge') or str(__import__('pathlib').Path(__import__('os').environ.get('ProgramFiles(x86)', '')) / 'Microsoft/Edge/Application/msedge.exe'))"
        elif 'default-workspace' in value:
            replacement = "str(__import__('pathlib').Path.cwd())"
        else:
            replacement = "str(_CHEMCLAW_ROOT / 'runtime')"
        edits.append((offsets[node.lineno - 1] + node.col_offset, offsets[node.end_lineno - 1] + node.end_col_offset, replacement.encode()))
    # Office adapters run with Python, including legacy entry points whose NODE was a literal.
    if office:
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'NODE' for target in node.targets):
                a = offsets[node.value.lineno - 1] + node.value.col_offset
                b = offsets[node.value.end_lineno - 1] + node.value.end_col_offset
                edits = [edit for edit in edits if not (edit[0] >= a and edit[1] <= b)]
                edits.append((a, b, b"__import__('sys').executable"))
    for start, end, value in sorted(edits, reverse=True):
        raw = raw[:start] + value + raw[end:]
    result = raw.decode('utf-8')
    if '_CHEMCLAW_ROOT' in result:
        tree = ast.parse(result)
        insert = 0
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            insert = tree.body[0].end_lineno
        for item in tree.body:
            if isinstance(item, ast.ImportFrom) and item.module == '__future__':
                insert = max(insert, item.end_lineno)
        lines = result.splitlines(keepends=True)
        lines.insert(insert, "\n_CHEMCLAW_ROOT = next(parent for parent in __import__('pathlib').Path(__file__).resolve().parents if (parent / 'runtime/deliver.mjs').is_file())\n")
        result = ''.join(lines)
    compile(result, str(file), 'exec')
    file.write_text(result, encoding='utf-8')
    changed.append(str(file.relative_to(root)))
print(f'Updated {len(changed)} packaged Python scripts; source collection is unchanged.')
