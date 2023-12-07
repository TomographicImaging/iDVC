# GitHub Actions

## Building the Conda Package: [conda_build_and_publish](./conda_build_and_publish.yml)
This github action builds and tests the conda package, by using the [conda-package-publish-action](https://github.com/TomographicImaging/conda-package-publish-action)

When pushing to master *all* variants are built and tested.

When making an [annotated](https://git-scm.com/book/en/v2/Git-Basics-Tagging) tag, *all* variants are built, tested and published to the [ccpi conda channel for idvc](https://anaconda.org/ccpi/idvc/files). This includes linux, windows and macOS versions.

When opening or modifying a pull request to master, a single variant is built and tested, but not published. This variant is `python=3.7` and `numpy=1.18`.

## Building/Publishing Documentation: [conda_build_and_publish](./conda_build_and_publish.yml)

This github action builds and optionally publishes the documentation located in [docs/source](../../docs/source).

The github action has two jobs:

1. [docs](./conda_build_and_publish.yml#L29):
-  builds the documentation with sphinx
-  uses upload-artifact to upload the html files which may then be used by **publish**

2. [publish](./conda_build_and_publish.yml#L42):
-  uses download-artifact to retrieve the built html files
-  pushes the html files to the gh-pages branch

When opening or modifying a pull request to master, `build` is run, but not `publish`.

When pushing to master or tagging, the documentation is built *and* published (both the `build` and `publish` jobs are run).

### Viewing Built Documentation
The `build` job builds the documentation and uploads it as an [artifact](./conda_build_and_publish.yml#L37),
in a folder named `DocumentationHTML`.
This can be found by going to the ‘Actions’ tab, and selecting the appropriate run of [conda_build_and_publish.yml](./conda_build_and_publish.yml).

When viewing the summary for the run of the action, there is an `Artifact` section at the bottom of the page.
Clicking on `DocumentationHTML` allows you to download a zip folder containing the built html files.
This allows you to preview the documentation site before it is published.

### Publication of the Documentation
The documentation is hosted on the [github site](https://tomographicimaging.github.io/iDVC/) associated with the repository.
This is built from the [gh-pages branch](https://github.com/TomographicImaging/iDVC/tree/gh-pages).

If you are an admin of the repository, you are able to see the settings for the site by going to `Settings->Pages`.

To publish the documentation, the publish job of the gh-action pushes the documentation changes to the `gh-pages` branch.
Any push to this branch automatically updates the github site.

### Initial Setup of the Docs Site & Action
To get the action to work I first had to:
1. [Create a gh-pages branch](https://gist.github.com/ramnathv/2227408) - note this only worked in bash, not windows command line.
2. Make the repo public
3. [Set the source](https://github.com/TomographicImaging/iDVC/settings/pages) for our github pages to be the gh-pages branch.

I followed the examples on the [sphinx build action page](https://github.com/marketplace/actions/sphinx-build), specifically this [example workflow](https://github.com/ammaraskar/sphinx-action-test/blob/master/.github/workflows/default.yml)
