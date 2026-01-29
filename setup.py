from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="latzero",
    version="0.3.0",
    author="BRAHMAI",
    author_email="hello@brahmai.in",
    description="Zero-latency, zero-fuss shared memory for Python — dynamic, encrypted, and insanely fast.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Latency-Zero/python-client",
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={
        "latzero": ["py.typed"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=[
        "cryptography>=3.4",
        "psutil>=5.8",
    ],
    extras_require={
        "fast": ["msgpack>=1.0"],
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.20",
            "pytest-cov>=4.0",
            "mypy>=1.0",
            "ruff>=0.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "latzero=latzero.cli.main:main",
        ],
    },
)
