from setuptools import setup, find_packages

setup(
    name='biju-cli',
    version='2.0.1',
    description='An advanced AI CLI + TUI developed by Prithish',
    author='Prithish',
    packages=find_packages(),
    install_requires=[
        'openai',
        'rich',
        'prompt_toolkit',
        'textual>=0.47.0',   # Biju TUI requirement
    ],
    entry_points={
        'console_scripts': [
            # Classic prompt_toolkit CLI (fallback)
            'biju-classic=biju.bijucli:main',
            # New Textual TUI (main)
            'biju=tui.app:main',
            'bijutui=tui.app:main',
        ],
    },
)
