"""Setup module installation."""

import os
import re

from setuptools import find_packages, setup

if __name__ == "__main__":
    MODULE_NAME = "todus"
    DESC = "ToDus client"
    URL = "https://github.com/adbenitez/todus"

    with open(os.path.join(MODULE_NAME, "__init__.py")) as fh:
        version = re.search(r"__version__ = \"(.*?)\"", fh.read(), re.M).group(1)

    with open("README.rst") as fh:
        long_description = fh.read()

    with open("requirements.txt", encoding="utf-8") as req:
        install_requires = [
            line.replace("==", ">=")
            for line in req.read().split("\n")
            if line and not line.startswith(("#", "-"))
        ]
    with open("requirements-test.txt", encoding="utf-8") as req:
        test_deps = [
            line.replace("==", ">=")
            for line in req.read().split("\n")
            if line and not line.startswith(("#", "-"))
        ]

    setup(
        name=MODULE_NAME,
        version=version,
        description=DESC,
        long_description=long_description,
        long_description_content_type="text/x-rst",
        author="adbenitez",
        author_email="adbenitez@nauta.cu",
        url=URL,
        keywords="todus",
        license="MPL",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: Plugins",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
            "Operating System :: OS Independent",
            "Topic :: Utilities",
        ],
        zip_safe=False,
        include_package_data=True,
        packages=find_packages(),
        install_requires=install_requires,
        extras_require={"test": test_deps},
    )
