import os
import mimetypes
import sys

# Max size for a single file (250 KB).
MAX_FILE_SIZE_BYTES = 250 * 1024 

def is_binary(file_path):
    mime, _ = mimetypes.guess_type(file_path)
    if mime and not mime.startswith('text/'):
        return True
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except Exception:
        return True

def crawl_and_dump(start_dir='.', output_filename='aggregated_files.txt'):
    skip_extensions = {
        '.log', '.bin', '.exe', '.dat', '.png', '.jpg', '.jpeg', '.gif', '.pyc', 
        '.sqlite3', '.db', '.pdf', '.svg', '.ico', '.woff', '.woff2', '.ttf', 
        '.eot', '.map', '.sql', '.csv', '.tsv', '.zip', '.tar', '.gz', '.bak', 
        '.pyo', '.pyd', '.so', '.dll', '.class', '.pem', '.crt', '.key',
        # NEW: Ignore Docs and Mobile/Desktop Apps
        '.md', '.mdx', '.prose', '.swift', '.kt', '.java', '.plist', '.pbxproj', '.storyboard', '.xib'
    }
    
    skip_dirs = {
        '.git', '__pycache__', 'node_modules', '.pnpm', 'logs', 'backups', 'attachments', 
        'data-tibor', 'data-liz', 'data-family-girschele', 
        'venv', '.venv', 'env', '.env', '.tox', 'site-packages',
        'dist', 'build', 'out', '.next', '.cache', 'coverage', 
        'pgdata', 'postgres', 'redis', 'db', 'database', 'data',
        '.vscode', '.idea', 'playwright-report', 'test-results',
        'vendor', 'public', 'static', 'assets', '.yarn',
        # NEW: Ignore doc folders, app folders, and translation files
        'docs', 'apps', 'locales', 'translations', 'i18n'
    }

    skip_exact_files = {
        'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 
        'poetry.lock', 'Pipfile.lock', 'Cargo.lock', 'Gemfile.lock'
    }

    output_path = os.path.abspath(output_filename)

    with open(output_path, 'w', encoding='utf-8') as out_f:
        for root, dirs, files in os.walk(start_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                if file == output_filename or file in skip_exact_files:
                    continue

                file_lower = file.lower()
                
                # NEW: Skip automated test files. LLMs don't need to read 10,000 tests to understand the core logic.
                if '.test.' in file_lower or '.spec.' in file_lower:
                    continue

                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in skip_extensions or 'log' in file_lower or file.endswith('.min.js') or file.endswith('.min.css'):
                    continue
                    
                try:
                    if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

                if is_binary(file_path):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        
                        if not content.strip():
                            continue
                        
                        out_f.write(f"\n{'='*60}\n")
                        out_f.write(f"FILE: {file_path}\n")
                        out_f.write(f"{'='*60}\n")
                        out_f.write(content + "\n")
                        
                except Exception:
                    pass 
    
    return output_path

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    output_file = 'aggregated_files.txt'
    
    print(f"Crawling directory: {os.path.abspath(target_dir)} ...")
    final_output_path = crawl_and_dump(target_dir, output_file)
    
    try:
        size_mb = os.path.getsize(final_output_path) / (1024 * 1024)
        print(f"\n✅ Done! Dump saved to:\n{final_output_path}")
        print(f"📦 Total File Size: {size_mb:.2f} MB\n")
    except Exception:
        pass