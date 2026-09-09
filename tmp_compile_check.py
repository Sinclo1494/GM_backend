import py_compile
import sys
import os

errors = []

for root, dirs, files in os.walk('api'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f'{path}: {e}')

py_count = sum(1 for r, d, fs in os.walk('api') for f in fs if f.endswith('.py'))

if errors:
    for err in errors:
        print(f'SYNTAX ERROR: {err}')
    sys.exit(1)
else:
    print(f'All {py_count} Python files compiled successfully')
