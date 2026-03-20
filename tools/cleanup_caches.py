"""Recursively remove Python cache files and common OS temp files.
Run from repo root: python tools/cleanup_caches.py
"""
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print('Cleaning repo root:', ROOT)
removed = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip .git
    if '.git' in dirpath.split(os.sep):
        continue
    # Remove __pycache__ directories
    if '__pycache__' in dirnames:
        p = os.path.join(dirpath, '__pycache__')
        try:
            shutil.rmtree(p)
            removed.append(p)
            print('Removed dir:', p)
        except Exception as e:
            print('Failed to remove dir', p, '->', e)
        # modify dirnames in-place so os.walk doesn't descend
        dirnames.remove('__pycache__')

    # Remove Thumbs.db and .pyc files
    for f in list(filenames):
        if f.endswith('.pyc') or f == 'Thumbs.db':
            fp = os.path.join(dirpath, f)
            try:
                os.remove(fp)
                removed.append(fp)
                print('Removed file:', fp)
            except Exception as e:
                print('Failed to remove file', fp, '->', e)

print('\nSummary: removed', len(removed), 'items')
for p in removed:
    print('-', p)
