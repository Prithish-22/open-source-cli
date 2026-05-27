from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='biju-cli',
    version='3.1.2',
    description='An advanced AI CLI + TUI developed by Prithish',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/prithish-22/biju",
    author='Prithish',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires='>=3.8',
    install_requires=[
        'openai',
        'rich',
        'prompt_toolkit',
        'textual>=0.47.0',   # Biju TUI requirement
    ],
    entry_points={
        'console_scripts': [
            # Classic prompt_toolkit CLI
            'biju=biju.bijucli:main',
            # New Textual TUI
            'bijutui=tui.app:main',
        ],
    },
)
