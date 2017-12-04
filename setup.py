from setuptools import setup

setup(
    name='snapkin',
    # version='0.1.0',
    author='JJ Quisenberry',
    py_modules=['snapkin'],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        snapkin=snapkin:cli
    ''',
)
