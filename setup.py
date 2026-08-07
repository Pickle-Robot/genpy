from setuptools import setup
setup(
    name='genpy',
    packages=['genpy'],
    package_dir={'': 'src'},
    requires=['genmsg'],
    version='0.7.17'
)