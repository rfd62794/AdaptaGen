"""
Setup script for AdaptaGen package.
"""

from setuptools import setup, find_packages

setup(
    name="adaptagen",
    version="0.0.2-r2",
    description="A self-modifying AI agent using the Gemini API",
    author="AdaptaGen Team",
    packages=find_packages(),
    install_requires=[
        "google-generativeai>=0.3.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "adaptagen=adaptagen.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
) 