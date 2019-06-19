from setuptools import setup, find_packages
from glob import glob
from os.path import basename
from os.path import splitext

setup(
    name='snapkin',
    version='0.1.0',
    description='btrfs snapshot clean up',
    author='JJ Quisenberry',
    author_email='johnny.e.quisenberry@gmail.com',
    packages=find_packages('src/snapkin'),
    package_dir={'': 'src/snapkin'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/snapkin/*.py')],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'bumpversion',
        'Click',
    ],
    entry_points='''
        [console_scripts]
        snapkin=snapkin:cli
    ''',
)
