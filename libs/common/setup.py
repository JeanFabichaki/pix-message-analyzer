from setuptools import setup, find_packages

setup(
    name="pix-guard-common",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.7.0",
        "pydantic-settings>=2.2.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "greenlet>=3.0.0",
        "asyncpg>=0.29.0",
        "aiosqlite>=0.20.0",
    ],
)
