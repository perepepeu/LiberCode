from setuptools import setup, find_packages

setup(
    name="libercode",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "rich>=13.0.0",
        "pyyaml>=6.0",
        "requests>=2.28.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "libercode=libercode.cli:main",
        ],
    },
)
