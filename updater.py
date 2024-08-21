# IMPORTS -------------------------------------------------------------------- #

import pandas as pd
import numpy as np
import os
import requests
import json
import re
from datetime import datetime
import time
from tqdm import tqdm

from bs4 import BeautifulSoup as bs4

import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

pd.set_option("display.max_rows", 50)

# CONSTANTS ------------------------------------------------------------------ #

# Set constants for data provider and data API.
PROVIDER = "Berlin Open Data"
PROVIDER_LINK = "https://daten.berlin.de/"
BASELINK_DATAPORTAL = "https://daten.berlin.de/datensaetze/"
CKAN_API_LINK = (
    "https://datenregister.berlin.de/api/3/action/current_package_list_with_resources"
)


# Set constants in regard to GitHub account and repo.
GITHUB_ACCOUNT = "tifa365"
REPO_NAME = "starter-code_open_data_berlin"
REPO_BRANCH = "main"
NOTEBOOKS_FOLDER = "notebooks/"
REPO_RMARKDOWN_OUTPUT = NOTEBOOKS_FOLDER + "01_r-markdown/"
REPO_PYTHON_OUTPUT = NOTEBOOKS_FOLDER + "02_python/"
TEMP_PREFIX = "_work/"


# Set local folders and file names.
TEMPLATE_FOLDER = "_templates/"
# Template for the README.md in the repo.
TEMPLATE_README = "template_md_readme.md"
# Header for list overview that is rendered as a GitHub page.
TEMPLATE_HEADER = "template_md_header.md"
TEMPLATE_PYTHON = "template_python.ipynb"
TEMPLATE_RMARKDOWN = "template_rmarkdown.Rmd"
METADATA_FOLDER = "_metadata_json/"

TODAY_DATE = datetime.today().strftime("%Y-%m-%d")
TODAY_DATETIME = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

# Set max length of dataset title in markdown table.
TITLE_MAX_CHARS = 200

# Sort markdown table by this feature.
SORT_TABLE_BY = "title"


# In[14]:


# Updated field sets from the Zuerich schema
KEYS_DATASET = [
    "organization.display_name",
    "organization.url",
    "maintainer",
    "maintainer_email",
    "tags",  # changed from "keywords"
    "date_released",  # changed from "issued"
    "metadata_created",
    "metadata_modified",
]

KEYS_DISTRIBUTIONS = [
    "package_id",
    "notes",  # changed from "description"
    "date_released",  # changed from "issued"
    "date_updated",  # changed from "modified"
    "license_title",  # changed from "rights"
]

REDUCED_FEATURESET = [
    "maintainer",
    "date_released",  # changed from "issued"
    "maintainer_email",
    "id",
    "metadata_created",
    "metadata_modified",
    "resources",
    "groups",
    "name",
    "url",
    "title",
    "notes",
    "author",
    "author_email",
    "version",
    "license_title",
    "license_url",
]


# In[15]:


# FUNCTIONS ------------------------------------------------------------------ #


# Retrieving data from the Berlin data register API, processing it, and saving it to CSV files
def get_full_package_list(limit=500, sleep=2):
    """Get full package list from CKAN API"""
    offset = 0
    frames = []
    while True:
        print(f"{offset} packages retrieved.")
        url = CKAN_API_LINK + f"?limit={limit}&offset={offset}"
        res = requests.get(url)
        data = json.loads(res.content)
        if data["result"] == []:
            break
        data = pd.DataFrame(pd.json_normalize(data["result"]))
        frames.append(data)
        offset += limit
        time.sleep(sleep)
    data = pd.concat(frames)
    data.reset_index(drop=True, inplace=True)
    return data


# In[16]:


# FILTER PROCESS ------------------------------------------------------------------ #


def has_csv_distribution(dists):
    """Iterate over package resources and keep only CSV entries in list"""
    csv_dists = [x for x in dists if x.get("format", "") == "CSV"]
    if csv_dists != []:
        return csv_dists
    else:
        return np.nan


def filter_csv(data):
    """Remove all datasets that have no CSV distribution"""
    data.resources = data.resources.apply(has_csv_distribution)
    data.dropna(subset=["resources"], inplace=True)
    return data.reset_index(drop=True)


# In[17]:


# CLEANING DATASETS ------------------------------------------------------------------ #


# Cleans and preprocesses dataset features, including tags, organization URLs, notes, and titles.
def clean_features(data):
    """Clean various features"""
    # Reduce tags to tag names if the column exists
    if "tags" in data.columns:
        data["tags"] = data["tags"].apply(
            lambda x: (
                [tag["name"] for tag in x]
                if isinstance(x, list)
                and all(isinstance(tag, dict) and "name" in tag for tag in x)
                else x
            )
        )

    if "groups" in data.columns:
        data["groups"] = data["groups"].apply(
            lambda groups: [
                {
                    **group,
                    "display_name": (
                        "No name provided"
                        if group.get("display_name", "") == ""
                        else group["display_name"]
                    ),
                    "url": (
                        "No group url provided"
                        if group.get("url", "") == ""
                        else group["url"]
                    ),
                }
                for group in groups
            ]
        )

    # Replace empty urls with NA message if the column exists
    if "organization.image_url" in data.columns:
        data.loc[data["organization.image_url"] == "", "organization.image_url"] = (
            "None provided"
        )

    # Remove HTML tags from notes (previously description) if the column exists
    if "notes" in data.columns:
        data["notes"] = data["notes"].apply(
            lambda x: bs4(x, "html.parser").text if isinstance(x, str) else x
        )

    # Strip whitespace from title if the column exists
    if "title" in data.columns:
        data["title"] = data["title"].apply(
            lambda x: x.strip() if isinstance(x, str) else x
        )

    return data


# PREPARE NOTEBOOKS ------------------------------------------------------------------ #


def prepare_data_for_codebooks(data, limit=None):
    """
    Prepares metadata from Berlin Open Data catalogue by creating formatted strings
    for metadata, contact information, and distributions. It also extracts distribution links.

    Args:
    data (pd.DataFrame): The input DataFrame containing the datasets.
    limit (int, optional): If provided, limits the number of datasets to process.

    Returns:
    pd.DataFrame: The processed DataFrame.
    """
    # Optionally limit the data to the specified number of datasets
    if limit is not None:
        data = data.head(limit).copy()
    else:
        data = data.copy()

    # Add new features to save prepared data
    data["metadata"] = None
    data["contact"] = None
    data["distributions"] = None
    data["distribution_links"] = None

    # Iterate over datasets and create additional data for markdown and code cells
    for idx in tqdm(data.index, desc="Processing datasets"):
        # Create metadata string, skipping any keys that don't exist in the data
        md = []
        for k in KEYS_DATASET:
            if k in data.columns:
                md.append(f"- **{k.capitalize()}** `{data.loc[idx, k]}`\n")
        data.loc[idx, "metadata"] = "".join(md)
        print(data.metadata)

        # Create contact information
        if "maintainer" in data.columns and "maintainer_email" in data.columns:
            if data.loc[idx, "maintainer"] and data.loc[idx, "maintainer_email"]:
                data.loc[idx, "contact"] = (
                    f"{data.loc[idx, 'maintainer']} | {data.loc[idx, 'maintainer_email']}"
                )
            else:
                data.loc[idx, "contact"] = "No contact information provided."
        else:
            data.loc[idx, "contact"] = "Contact information not available in dataset."

        print(f"Contact after assignment: {data.loc[idx, 'contact']}")

        tmp_dists = []
        tmp_links = []
        if "resources" in data.columns:
            for dist in data.loc[idx, "resources"]:
                # Remove line breaks from description
                if isinstance(dist.get("description"), str):
                    dist["description"] = re.sub(r"[\n\r]+", " ", dist["description"])
                else:
                    dist["description"] = ""

                # Get other metadata of distribution
                md = [
                    f"# {k.capitalize():<25}: {dist.get(k, None)}\n"
                    for k in KEYS_DISTRIBUTIONS
                    if k in dist
                ]
                tmp_dists.append("".join(md))

                # In a few cases the dataset has no download_url but rather is available at "url".
                csv_url = dist.get("url", "")
                tmp_links.append(csv_url)

        # Use .at[] for better performance when setting values
        data.at[idx, "distributions"] = tmp_dists
        data.at[idx, "distribution_links"] = tmp_links

    # Sort values for table
    if "title" in data.columns:
        data.sort_values("title", inplace=True)
    data.reset_index(drop=True, inplace=True)

    # Only return columns that exist in the DataFrame
    # return data[[col for col in REDUCED_FEATURESET if col in data.columns]]
    return data


# In[19]:


# CREATE PYTHON NOTEBOOKS ------------------------------------------------------------------ #


def create_python_notebooks(data):
    """Create Jupyter Notebooks with Python starter code and save to 'notebooks' folder"""

    # Create 'notebooks/python' folder if it doesn't exist
    python_notebooks_folder = os.path.join(os.getcwd(), "notebooks", "python")
    os.makedirs(python_notebooks_folder, exist_ok=True)

    for idx in tqdm(data.index, desc="Creating notebooks"):
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_PYTHON}") as file:
            py_nb = file.read()

        # Populate template with metadata
        py_nb = py_nb.replace("{{ PROVIDER }}", PROVIDER)

        title = re.sub('"', "'", data.loc[idx, "title"])
        py_nb = py_nb.replace("{{ DATASET_TITLE }}", title)

        description = data.loc[idx, "notes"]
        description = re.sub('"', "'", description)
        description = re.sub("\\\\", "|", description)
        py_nb = py_nb.replace("{{ DATASET_DESCRIPTION }}", description)

        py_nb = py_nb.replace("{{ DATASET_IDENTIFIER }}", data.loc[idx, "id"])
        py_nb = py_nb.replace(
            "{{ DATASET_METADATA }}", re.sub('"', "'", data.loc[idx, "metadata"])
        )
        py_nb = py_nb.replace(
            "{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"]))
        )
        # Adjust BASELINK_DATAPORTAL for Berlin dataset
        BASELINK_DATAPORTAL = (
            "https://datenregister.berlin.de/api/3/action/package_show?id="
        )
        url = f'[Direct link by {PROVIDER} for dataset]({BASELINK_DATAPORTAL}{data.loc[idx, "name"]})'
        py_nb = py_nb.replace("{{ DATASHOP_LINK_PROVIDER }}", url)

        if data.loc[idx, "url"] is not None:
            org_name = data.loc[idx, "organization.title"]
            url = data.loc[idx, "url"]
            url = f"[Direct link by {org_name} for dataset]({url})"
            py_nb = py_nb.replace("{{ DATASHOP_LINK_ORGANIZATION }}", url)

        py_nb = py_nb.replace("{{ CONTACT }}", data.loc[idx, "contact"])

        py_nb = json.loads(py_nb, strict=False)

        # Find code cell for dataset imports
        for id_cell, cell in enumerate(py_nb["cells"]):
            if cell["id"] == "0":
                dist_cell_idx = id_cell
                break

        # Iterate over distributions and create metadata comments and code
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(
            zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])
        ):
            code = (
                f"# Distribution {id_dist}\n{dist}\ndf = get_dataset('{dist_link}')\n"
            )
            code = "".join([f"{line}\n" for line in code.split("\n")])
            code_block.append(code)

        # Populate code block with data for all distributions
        code_block = "".join(code_block)
        py_nb["cells"][dist_cell_idx]["source"] = code_block

        # Save to disk in the 'notebooks' folder
        notebook_filename = f'{data.loc[idx, "id"]}.ipynb'
        notebook_path = os.path.join(python_notebooks_folder, notebook_filename)
        with open(notebook_path, "w", encoding="utf-8") as file:
            json.dump(py_nb, file, ensure_ascii=False, indent=2)

    print(f"Notebooks saved in: {python_notebooks_folder}")


# In[20]:


# CREATE R NOTEBOOKS ------------------------------------------------------------------ #


def create_r_notebooks(data):
    """Create R Markdown files with R starter code and save to 'notebooks/rmarkdown' folder"""

    # Create 'notebooks/rmarkdown' folder if it doesn't exist
    r_notebooks_folder = os.path.join(os.getcwd(), "notebooks", "rmarkdown")
    os.makedirs(r_notebooks_folder, exist_ok=True)

    for idx in tqdm(data.index, desc="Creating R notebooks"):
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_RMARKDOWN}") as file:
            rmd = file.read()

        # Populate template with metadata
        rmd = rmd.replace("{{ PROVIDER }}", PROVIDER)

        title = re.sub('"', "'", data.loc[idx, "title"])
        rmd = rmd.replace("{{ DATASET_TITLE }}", title)

        description = data.loc[idx, "notes"]
        description = re.sub('"', "'", description)
        description = re.sub("\\\\", "|", description)
        rmd = rmd.replace("{{ DATASET_DESCRIPTION }}", description)

        rmd = rmd.replace("{{ DATASET_IDENTIFIER }}", data.loc[idx, "id"])
        rmd = rmd.replace(
            "{{ DATASET_METADATA }}", re.sub('"', "'", data.loc[idx, "metadata"])
        )
        rmd = rmd.replace(
            "{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"]))
        )

        # Adjust BASELINK_DATAPORTAL for Berlin dataset
        BASELINK_DATAPORTAL = (
            "https://datenregister.berlin.de/api/3/action/package_show?id="
        )
        url = f'[Direct link by {PROVIDER} for dataset]({BASELINK_DATAPORTAL}{data.loc[idx, "name"]})'
        rmd = rmd.replace("{{ DATASHOP_LINK_PROVIDER }}", url)

        if data.loc[idx, "url"] is not None:
            org_name = data.loc[idx, "organization.title"]
            url = data.loc[idx, "url"]
            url = f"[Direct link by {org_name} for dataset]({url})"
            rmd = rmd.replace("{{ DATASHOP_LINK_ORGANIZATION }}", url)

        rmd = rmd.replace("{{ CONTACT }}", data.loc[idx, "contact"])

        # Create code blocks for all distributions
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(
            zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])
        ):
            code = (
                f"# Distribution {id_dist}\n{dist}\ndf <- read.csv('{dist_link}')\n\n"
            )
            code_block.append(code)

        rmd = rmd.replace("{{ DISTRIBUTIONS }}", "".join(code_block))

        # Save to disk in the 'notebooks/rmarkdown' folder
        notebook_filename = f'{data.loc[idx, "id"]}.Rmd'
        notebook_path = os.path.join(r_notebooks_folder, notebook_filename)
        with open(notebook_path, "w", encoding="utf-8") as file:
            file.write(rmd)

    print(f"R notebooks saved in: {r_notebooks_folder}")


def get_header(dataset_count):
    """Retrieve README template and populate with all necessary variables."""
    with open(f"{TEMPLATE_FOLDER}{TEMPLATE_README}") as file:
        content = file.read()

    # Replace all variables
    content = re.sub("{{ PROVIDER }}", PROVIDER, content)
    content = re.sub(
        "{{ GITHUB_REPO }}", f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}", content
    )
    content = re.sub("{{ DATASET_COUNT }}", str(int(dataset_count)), content)
    content = re.sub("{{ DATA_PORTAL }}", PROVIDER_LINK, content)
    content = re.sub("{{ TODAY_DATE }}", TODAY_DATETIME, content)

    return content


def create_overview(data, header):
    """Create README with link table."""
    baselink_r_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_RMARKDOWN_OUTPUT}"
    baselink_py_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"
    baselink_py_colab = f"https://githubtocolab.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"

    md_doc = []
    md_doc.append(header)
    md_doc.append(
        f"| ID | Title (abbreviated to {TITLE_MAX_CHARS} chars) | Python Colab | Python GitHub | R GitHub |\n"
    )
    md_doc.append("| :-- | :-- | :-- | :-- | :-- |\n")

    for idx in tqdm(data.index):
        identifier = data.loc[idx, "id"]
        # Remove square brackets from title, since these break markdown links.
        title_clean = data.loc[idx, "title"].replace("[", " ").replace("]", " ")
        if len(title_clean) > TITLE_MAX_CHARS:
            title_clean = title_clean[:TITLE_MAX_CHARS] + "…"

        ds_link = f"{BASELINK_DATAPORTAL}{identifier}"

        r_gh_link = f"[R GitHub]({baselink_r_gh}{identifier}.Rmd)"
        py_gh_link = f"[Python GitHub]({baselink_py_gh}{identifier}.ipynb)"
        py_colab_link = f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({baselink_py_colab}{identifier}.ipynb)"

        md_doc.append(
            f"| {identifier} | [{title_clean}]({ds_link}) | {py_colab_link} | {py_gh_link} | {r_gh_link} |\n"
        )

    md_doc = "".join(md_doc)

    with open(f"{TEMP_PREFIX}README.md", "w") as file:
        file.write(md_doc)


def main():
    # Get full package list
    all_packages = get_full_package_list()

    # Apply filtering
    packages_before = all_packages.shape[0]
    print(f"Number of packages before filtering: {packages_before}")
    df = filter_csv(all_packages)
    print(df.head(2))
    packages_after = df.shape[0]
    print(f"Number of packages after filtering: {packages_after}")
    difference = packages_before - packages_after
    print(f"Number of packages removed by filtering: {difference}")

    # Clean features and prepare the data
    df = clean_features(df)
    df = prepare_data_for_codebooks(df)

    # Create notebooks
    create_python_notebooks(df)
    create_r_notebooks(df)

    # Create overview (commented out for now)
    header = get_header(dataset_count=len(df))
    create_overview(df, header)


if __name__ == "__main__":
    main()
