from distutils.core import setup


with open("README.md", "r", encoding="utf-8") as f:
  long_description = f.read()


setup(
  name="Resource Locator Program",
  version="0.0.4",
  description="Resource Locator Program",
  long_description=long_description,
  long_description_content_type="text/markdown",
  author="Rick Wierenga",
  author_email="rick_wierenga@icloud.com",
  url="https://www.github.com/pylabrobot/resource-locator-program/",
  install_requires=["pylabrobot"],
  packages=["resource_locator_program"],
)
