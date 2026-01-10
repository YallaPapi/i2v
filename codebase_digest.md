Debug: Final ignore patterns: {'.gitignore', 'dist', '.git', '*.pyo', '*.log', '*.so', '*.tmp', 'env', '*.dll', '*.swp', '*.pyd', '.hg', '*.bak', 'venv', 'build', 'node_modules,__pycache__,.git,*.pyc,*.lock,package-lock.json,*.egg-info,dist,build,.next,frontend/node_modules,frontend/.next,downloads,*.mp4,*.png,*.jpg,*.jpeg,*.gif,*.webp,*.ico', '.svn', '.venv', '__pycache__', '*.pyc', '*.dylib', '.DS_Store', 'bower_components', '*.egg-info', 'Thumbs.db', '.vscode', 'node_modules', '.idea'}
Debug: Ignore patterns after load_ignore_patterns: {'.gitignore', 'dist', '.git', '*.pyo', '*.log', '*.so', '*.tmp', 'env', '*.dll', '*.swp', '*.pyd', '.hg', '*.bak', 'venv', 'build', 'node_modules,__pycache__,.git,*.pyc,*.lock,package-lock.json,*.egg-info,dist,build,.next,frontend/node_modules,frontend/.next,downloads,*.mp4,*.png,*.jpg,*.jpeg,*.gif,*.webp,*.ico', '.svn', '.venv', '__pycache__', '*.pyc', '*.dylib', '.DS_Store', 'bower_components', '*.egg-info', 'Thumbs.db', '.vscode', 'node_modules', '.idea'}
+-----------------+
| Codebase Digest |
+-----------------+
Analyzing directory: .
Debug: Ignoring .\.git due to pattern .git
Debug: Ignoring .\.venv due to pattern .venv
Debug: Ignoring .\.gitignore due to pattern .gitignore
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\asus\AppData\Local\Programs\Python\Python314\Scripts\cdigest.exe\__main__.py", line 6, in <module>
    sys.exit(main())
             ~~~~^^
  File "C:\Users\asus\AppData\Local\Programs\Python\Python314\Lib\site-packages\codebase_digest\app.py", line 393, in main
    estimated_size = estimate_output_size(args.path, ignore_patterns, args.path)
  File "C:\Users\asus\AppData\Local\Programs\Python\Python314\Lib\site-packages\codebase_digest\app.py", line 324, in estimate_output_size
    if not should_ignore(file_path, base_path, ignore_patterns) and is_text_file(file_path):
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\asus\AppData\Local\Programs\Python\Python314\Lib\site-packages\codebase_digest\app.py", line 54, in should_ignore
    rel_path = os.path.relpath(path, base_path)
  File "<frozen ntpath>", line 807, in relpath
ValueError: path is on mount '\\\\.\\nul', start on mount 'C:'
