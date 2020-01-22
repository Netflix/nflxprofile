import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nflxprofile",
    version="1.4.3",
    author="Matheus Marchini",
    author_email="mmarchini@netflix.com",
    description="Protobuf specification of the nflxprofile format",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Netflix/nflxprofile",
    packages=setuptools.find_packages(),
    install_requires=['protobuf'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'nflxprofile = nflxprofile.cli:main'
        ]
    }
)
