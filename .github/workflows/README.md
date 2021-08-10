# GitHub Actions

## Building the Conda Package: [conda_build_and_publish](https://github.com/TomographicImaging/iDVC/blob/master/.github/workflows/conda_build_and_publish.yml)
This github action builds and tests the conda package, by using the [conda-package-publish-action](https://github.com/paskino/conda-package-publish-action)

If pushing to master or tagging, *all* variants are built, tested and published to the [ccpi conda channel for idvc](https://anaconda.org/ccpi/ccpi-dvc/files).

If opening or modifying a pull request to master, a single variant is built and tested, but not published.

## Building/Publishing Documentation: [docs_build_and_publish](https://github.com/TomographicImaging/iDVC/blob/master/.github/workflows/docs_build_and_publish.yml)

This github action builds and optionally publishes the documentation located in [docs/source](https://github.com/TomographicImaging/iDVC/tree/master/docs/source). 

The github action has two jobs:
[build](https://github.com/TomographicImaging/iDVC/blob/39d2685395c36fa5acc93f38f9db37af10eb2f9c/.github/workflows/docs_build_and_publish.yml#L12)
and [publish](https://github.com/TomographicImaging/iDVC/blob/39d2685395c36fa5acc93f38f9db37af10eb2f9c/.github/workflows/docs_build_and_publish.yml#L27).

If opening or modifying a pull request to master, `build` is run, but not `publish`.
If pushing to master or tagging, the documentation is built *and* published (both the `build` and `publish` jobs are run).

### Viewing Built Documentation
The `build` job builds the documentation and uploads it as an [artifact](https://github.com/TomographicImaging/iDVC/blob/39d2685395c36fa5acc93f38f9db37af10eb2f9c/.github/workflows/docs_build_and_publish.yml#L21),
in a folder named `DocumentationHTML`.
This can be found by going to the ‘Actions’ tab, and selecting the appropriate run of `.github/workflows/docs_build_and_publish.yml`.

When viewing the summary for the run of the action, there is an `Artifact` section at the bottom of the page.
Clicking on `DocumentationHTML` allows you to download a zip folder containing the built html files.
This allows you to preview the documentation site before it is published.

### Publication of the Documentation
The documentation is hosted on the [github site](https://tomographicimaging.github.io/iDVC/) associated with the repository.
This is built from the [gh-pages branch](https://github.com/TomographicImaging/iDVC/tree/gh-pages). 

If you are an admin of the repository, you are able to see the settings for the site by going to `Settings->Pages`.

To publish the documentation, the publish job of the gh-action pushes the documentation changes to the `gh-pages` branch.
Any push to this branch automatically updates the github site.


