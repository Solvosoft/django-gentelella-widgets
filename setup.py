'''
Created on 12/02/2020

@author: luisza
'''

import os

from setuptools import setup, find_packages

CLASSIFIERS = [
    'Environment :: Web Environment',
    'Framework :: Django',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
]

README = open(os.path.join(os.path.dirname(__file__), 'Readme.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))
version = '0.4.0'

setup(
    author='Luis Zarate Montero',
    author_email='luis.zarate@solvosoft.com',
    name='djgentelella',
    version=version,
    description='Extra widgets for django using gentelella.',
    long_description=README,
    url='https://solvosoft.com',
    license='GNU General Public License',
    platforms=['OS Independent'],
    classifiers=CLASSIFIERS,
    install_requires=[
        'django-tree-queries>=0.11.0',
        'djangoajax>=3.3',
        'django-markitup>=4.0.0',
        'markdown',
        "pillow>=10.3.0",
        "djangorestframework>=3.15.2",
        'django>=4.2',
        'django_filter>=22.1',
        "django-cors-headers==4.6.0",
        "uvicorn==0.32.1",
        "uvicorn-worker==0.2.0",
        "channels==4.2.0",
        "wsproto==1.2.0",
        "requests==2.32.3"
    ],
    packages=find_packages(exclude=["demo", 'doc']),
    include_package_data=True,
    zip_safe=False
)
