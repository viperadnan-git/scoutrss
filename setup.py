from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()
setup(
    name="scoutrss",
    version="0.1.0",
    description="A library for watching RSS feeds and notifying when new entries are available",
    author="Adnan Ahmad",
    author_email="viperadnan@gmail.com",
    url="https://github.com/viperadnan-git/scoutrss",
    license="GNU General Public License v3.0",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=find_packages(),
    install_requires=[
        "pickledb",
        "apscheduler",
        "feedparser",
    ],
)
