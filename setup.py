from setuptools import setup, find_packages

setup(
    name='biju-cli',
    version='1.0.0',
    description='An advanced AI CLI developed by Prithish',
    author='Prithish',
    packages=find_packages(),
    install_requires=[
        'openai',
        'rich',
        'prompt_toolkit'
    ],
    entry_points={
        'console_scripts': [
            # THIS is the magic line. 
            # It says: When the user types "biju", run the main() function inside bijucli.py
            'biju=biju.bijucli:main',  
        ],
    },
)