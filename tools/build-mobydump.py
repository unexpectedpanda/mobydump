#!/usr/bin/env python

"""
Build script for MobyDump on Windows
"""

import pathlib
import shutil
import subprocess
import zipfile

def main():
# Set the zip compression
    compression: int = zipfile.ZIP_DEFLATED

    print('\nBuilding MobyDump...')

    # Delete folders that could cause issues
    delete_folders: list[str] = [
        'build//working/dist',
        'build/working/modules',
    ]

    for folder in delete_folders:
        try:
            shutil.rmtree(pathlib.Path(folder))
        except:
            pass

    # Create folders needed to build MobyDump
    create_folders: list[str] = [
        'build/working/dist',
        'build/files',
        'build/working',
    ]

    for folder in create_folders:
        pathlib.Path(folder).mkdir(parents=True, exist_ok=True)

    # Prevent PyInstaller from copying the MobyGames API key environment variable
    mobykey: str = ''

    with open (pathlib.Path('.env'), 'r', encoding='utf-8') as env_file:
        mobykey = env_file.read()

    with open (pathlib.Path('.env'), 'w', encoding='utf-8') as env_file:
        env_file.write('')

    # Copy required files for building the Windows binary
    destination_path: str = 'build/working'
    shutil.copyfile(pathlib.Path('mobydump.py'), pathlib.Path(f'{destination_path}/mobydump.py'))
    shutil.copytree(pathlib.Path('modules'), pathlib.Path(f'{destination_path}/modules'))

    # Get the version
    version: str = ''

    with open(pathlib.Path('modules/constants.py'), 'r') as input_file:
        for line in input_file:
            if '__version__' in line:
                version = line.replace('__version__ = \'', '')[:-2]
                break

    # Run Pyinstaller to generate the Windows binary
    subprocess.run('pyinstaller mobydump.py --upx-dir=c:/upx', cwd='build/working')

    # Compress to zip
    compress_files = list(pathlib.Path('build/working/dist/mobydump/').glob('**/*'))

    zf = zipfile.ZipFile(f'build/files/mobydump-{version.lower().replace(" ", "-")}-win-x86-64.zip', mode='w')

    home_path = pathlib.Path('build/working/dist/mobydump/')

    for file in compress_files:
        try:
            zf.write(file, str(pathlib.Path(file).relative_to(home_path)), compress_type=compression)
        except:
            pass

    zf.close()

    # Restore the .env file
    with open (pathlib.Path('.env'), 'w', encoding='utf-8') as env_file:
        env_file.write(mobykey)

    print('\nBuild complete.\n')

if __name__ == '__main__':
    main()