#!/usr/bin/env python3
path = '/Users/peteromalley/Documents/.megaplan-worktrees/capwaist/astrid/core/element/schema.py'
with open(path, 'r') as f:
    content = f.read()

# Fix the _validate_id line: the correct Python source is "\\" (escaped backslash → single \ char)
old_line = '    if not _ID_RE.match(value) or "/" in value or "\\" in value or value in {".", ".."}:'
# The correct line in Python source code should be:
new_line = '    if not _ID_RE.match(value) or "/" in value or "\\\\" in value or value in {".", ".."}:'

if old_line not in content:
    print("Old line not found. Checking content around line 448...")
    lines = content.split('\n')
    for i in range(445, min(450, len(lines))):
        print(f"Line {i+1}: {repr(lines[i])}")
else:
    print("Found old line, replacing...")
    content = content.replace(old_line, new_line, 1)
    with open(path, 'w') as f:
        f.write(content)
    print("Done")

# Also verify
with open(path, 'r') as f:
    lines = f.readlines()
print(f"Line 448 now: {repr(lines[447])}")
