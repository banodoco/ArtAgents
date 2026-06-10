path = '/Users/peteromalley/Documents/.megaplan-worktrees/capwaist/astrid/core/element/schema.py'
with open(path, 'rb') as f:
    content = f.read()

# 4 backslashes between quotes -> 2 backslashes between quotes
old = b'"\x5c\x5c\x5c\x5c"'
new = b'"\x5c\x5c"'
print(f'Replacing {old} with {new}')
print(f'Count before: {content.count(old)}')
content = content.replace(old, new)
print(f'Count after replace: {content.count(old)}')

with open(path, 'wb') as f:
    f.write(content)

# Verify
with open(path, 'rb') as f:
    content = f.read()
idx = content.find(b'def _validate_id')
chunk = content[idx:idx+200]
print(f'Chunk: {chunk[90:120]}')
