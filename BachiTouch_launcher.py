import os
import subprocess
import sys


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(base_dir, 'server_gui.exe')
    if not os.path.exists(exe_path):
        print('server_gui.exe not found. Build the PyInstaller executable first.')
        sys.exit(1)
    subprocess.Popen([exe_path], cwd=base_dir)


if __name__ == '__main__':
    main()
