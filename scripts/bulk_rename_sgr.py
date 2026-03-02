import os
from pathlib import Path

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return

    # Order matters!
    new_content = content
    
    # 1. Fix GitHub Repo URIs first
    new_content = new_content.replace('github.com/scarseze/sgr-kernel', 'github.com/scarseze/sgr-kernel')
    new_content = new_content.replace('github.com/scarseze/sgr-kernel', 'github.com/scarseze/sgr-kernel')
    new_content = new_content.replace('scarseze.github.io/sgr-kernel', 'scarseze.github.io/sgr-kernel')
    new_content = new_content.replace('scarseze/sgr-kernel', 'scarseze/sgr-kernel')
    
    # 2. Fix text mentions
    new_content = new_content.replace('SGR Kernel', 'SGR Kernel')
    new_content = new_content.replace('SGR Kernel', 'SGR Kernel')
    new_content = new_content.replace('SGR Kernel', 'SGR Kernel')  # typo fix from user prompt

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {filepath}")

def main():
    dirs_to_process = [
        r'c:\Users\macht\SA\sgr_kernel',
        r'c:\Users\macht\SA\ai_ml_playbook'
    ]
    
    extensions = {'.md', '.py', '.yml', '.yaml', '.json', '.txt', '.csv'}
    
    for d in dirs_to_process:
        for root, dirs, files in os.walk(d):
            # skip git and generated docs
            if '.git' in root or 'site_docs' in root or 'site' in root or '__pycache__' in root:
                continue
                
            for file in files:
                if Path(file).suffix in extensions:
                    replace_in_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
