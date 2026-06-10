import tempfile, os

# Test what's in the actual schema.py file at the problematic line
path = '/Users/peteromalley/Documents/.megaplan-worktrees/capwaist/astrid/core/element/schema.py'
with open(path, 'rb') as f:
    content = f.read()

# Find the _validate_id function
idx = content.find(b'def _validate_id(value')
# Get the line with backslashes
lines = content[idx:idx+200].split(b'\n')
for i, line in enumerate(lines):
    if b'in value' in line:
        print(f"Line bytes: {line}")
        print(f"Line repr: {line!r}")
        # Count backslashes in this line
        bs_count = line.count(92)  # 92 = ord('\\')
        print(f"Backslash count: {bs_count}")
        
# Now check what Python sees when parsing
with open(path, 'r') as f:
    source = f.read()
try:
    compile(source, path, 'exec')
    print("Compilation OK!")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    # Show the problematic line
    lines = source.split('\n')
    if e.lineno:
        for i in range(max(0, e.lineno-2), min(len(lines), e.lineno+1)):
            print(f"  {i+1}: {lines[i]!r}")
