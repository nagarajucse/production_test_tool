import os
import shutil
from pathlib import Path

def clean_project():
    project_root = Path(__file__).parent.resolve()
    
    # Things to remove
    directories_to_remove = ["__pycache__", ".pytest_cache"]
    extensions_to_remove = [".pyc", ".pyo", ".log"]
    specific_files_to_remove = ["Datasheet.xlsx"]
    
    print(f"Cleaning project at: {project_root}")
    
    count_dirs = 0
    count_files = 0

    for root, dirs, files in os.walk(project_root):
        # Skip .git and .venv directories
        if ".git" in dirs:
            dirs.remove(".git")
        if ".venv" in dirs:
            dirs.remove(".venv")
        if "venv" in dirs:
            dirs.remove("venv")

        # Remove directories
        for d in list(dirs):
            if d in directories_to_remove:
                dir_path = os.path.join(root, d)
                try:
                    shutil.rmtree(dir_path)
                    print(f"Removed directory: {dir_path}")
                    dirs.remove(d)  # Don't walk into removed directories
                    count_dirs += 1
                except Exception as e:
                    print(f"Failed to remove directory {dir_path}: {e}")

        # Remove files
        for f in files:
            file_path = os.path.join(root, f)
            if any(f.endswith(ext) for ext in extensions_to_remove) or f in specific_files_to_remove:
                try:
                    os.remove(file_path)
                    print(f"Removed file: {file_path}")
                    count_files += 1
                except Exception as e:
                    print(f"Failed to remove file {file_path}: {e}")

    print(f"\nCleanup complete! Removed {count_dirs} directories and {count_files} files.")
    print("The project is now ready to be moved or copied to another laptop.")

if __name__ == "__main__":
    clean_project()
