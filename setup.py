import sys
from setuptools import find_packages, setup

setup(
    name='elasticparse',
    version='0.0.1',
    install_requires=['pyparsing'],
    packages=find_packages(),
    long_description=open('README.md').read(),
    author='Matt Johnson',
)
