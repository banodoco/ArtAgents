path = '/Users/peteromalley/Documents/.megaplan-worktrees/capwaist/astrid/core/element/schema.py'
with open(path, 'rb') as f:
    content = f.read()

idx = content.find(b'def _validate_id')
chunk = content[idx:idx+200]

# Let me examine byte by byte around the backslashes
start = idx + 90
for i in range(start, start+30):
    b = content[i]
    if b == 0x5c:  # backslash
        print(f'Offset {i}: backslash, surrounding bytes: {list(content[i-3:i+5])}')
    elif b == 0x22:  # quote
        print(f'Offset {i}: quote, surrounding bytes: {list(content[i-3:i+5])}')
