from setuptools import setup, find_packages

setup(
    name="ai-scientist",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pypdf>=3.0.0",
        "openai>=1.0.0",
        "sentence-transformers>=2.2.0",
        "qdrant-client>=1.7.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-scientist=run_pipeline:main",
        ]
    },
)
