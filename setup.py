from distutils.core import setup


with open("README.md", "r") as f:
  long_description = f.read()


setup(name="Resource Locator Program",
  version="0.0.1",
  description="Resource Locator Program",
  long_description=long_description,
  long_description_content_type="text/markdown",
  author="Rick Wierenga",
  author_email="rick_wierenga@icloud.com",
  url="https://www.github.com/pylabrobot/resource-locator-program/",
  install_requires=["PyQt6", "pylabrobot"],
  packages=["resource_locator_program"],
  entry_points={
    "console_scripts": [
        "resource-locator-program = resource_locator_program.__main__:main"
    ]
  }
)
