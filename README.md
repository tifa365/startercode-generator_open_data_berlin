# 🚀 Starter Code Generator for Berlin Open Data

### Automatically generate Python and R starter code for the Berlin open data platform

## Overview
This repo provides a Python script that generates starter code notebooks from the metadata of Berlin's open data portal. You can execute the script manually or trigger it regularly (e.g., every night) with a GitHub Action that we provide here too, creating code notebooks for every dataset in Berlin's data shop.

The script also generates a README file that contains a list of all datasets and links to the corresponding notebooks, which you can use as an overview for your users. You can easily expose this as a website with GitHub Pages.

The execution of the script is lightweight and takes only a couple of minutes depending on the count of datasets in Berlin's data portal.

Your users get notebooks that are specifically tailored for every dataset in Berlin's open data catalog. They are already set with the most recent dataset metadata and code snippets. Your users can start their analysis for Berlin's datasets right away with just a couple of clicks, or even just one single click if they use Google Colab.

This repo is set up to generate the starter code [in this repo] (replace with your destination repo link) and creates [this overview page] (replace with your GitHub Pages link).

## How does it work?
The system works with two repos:
- The **first repo** (this one) contains the code that creates the notebooks and the overview README.
- The GitHub Action workflow included in this repo instantiates a container, installs the necessary dependencies, clones the repo, and executes the script.
- Once the notebooks are created, the workflow will push these to a **second repo** that you can make available for your users.

The script works with templates stored in the `_templates` directory. You can easily adapt these according to your ideas. Just make sure that you keep the necessary placeholders (marked with double curly brackets) in the templates. The script will replace them with values from the metadata.

The code is adapted to work with the [Berlin Open Data Portal](https://daten.berlin.de/).

## How to adapt the code to your needs?
(The steps remain the same as in the original README, but users should be aware that they need to adapt the parsing functions in `updater.py` to work with Berlin's data portal API)

## Dependencies
(This section remains the same as in the original README)

## Good to know
- This project is adapted from the work of the Team Data of the Statistical Office of the Canton Zürich and their [startercode generator](https://github.com/openZH/startercode-generator_openZH).
- It's also inspired by the [OGD team Thurgau's similar project](https://github.com/ogdtg/starter-code-ogdtg).
- This version is specifically tailored for the [Berlin Open Data Portal](https://daten.berlin.de/), providing easy access to Berlin's public datasets.

## Collaboration
Your ideas and contributions are very welcome, especially those that help improve accessibility and usability of Berlin's open data. Please open an issue or a pull request.