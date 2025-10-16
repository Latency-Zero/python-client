from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="latzero",
    version="0.1.5",
    author="BRAHMAI",
    description="Zero-latency, zero-fuss shared memory for Python — dynamic, encrypted, and insanely fast.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/latzero/latzero",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "cryptography",
        "psutil",
    ],
)
